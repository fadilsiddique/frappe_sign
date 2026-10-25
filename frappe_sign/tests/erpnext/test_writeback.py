"""Write-back on a submitted Sales Order (P2.6, DESIGN 4.5): sign_status through the envelope's life,
timeline comments, and the sealed PDF attached once."""

import unittest
from unittest.mock import patch

import frappe

from frappe_sign.jobs import seal as seal_job
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import signing, writeback
from frappe_sign.tests.doctypes import disable_doctypes, enable_doctypes
from frappe_sign.tests.erpnext.helpers import erpnext_installed, make_sales_order
from frappe_sign.tests.factories import make_profile, make_user, test_company
from frappe_sign.tests.integration.test_sealing import no_commits, offline_seal
from frappe_sign.tests.integration.test_signing_service import SigningCase
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now


class TestWriteback(SigningCase):
	@classmethod
	def setUpClass(cls):
		if not erpnext_installed():
			raise unittest.SkipTest("ERPNext is not installed")
		super().setUpClass()
		enable_doctypes("Sales Order")

	@classmethod
	def tearDownClass(cls):
		disable_doctypes("Sales Order")
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		self.order = make_sales_order()

	def sent(self, **template):
		draft = make_draft(
			publish_template(**template),
			reference_doctype="Sales Order",
			reference_name=self.order.name,
			company=test_company(),
		)
		self.box_ctx = capture_tokens()
		self.box = self.box_ctx.__enter__()
		self.addCleanup(self.box_ctx.__exit__, None, None, None)
		send_now(draft.name)
		self.name = draft.name
		writeback.on_sent(self.name)
		return self.name

	def order_values(self):
		return frappe.db.get_value(
			"Sales Order", self.order.name, ["sign_status", "sign_envelope", "docstatus"], as_dict=True
		)

	def comments(self) -> list[str]:
		return frappe.get_all(
			"Comment",
			filters={
				"reference_doctype": "Sales Order",
				"reference_name": self.order.name,
				"comment_type": "Info",
			},
			pluck="content",
			order_by="creation asc",
		)

	def attachments(self) -> list:
		return frappe.get_all(
			"File",
			filters={"attached_to_doctype": "Sales Order", "attached_to_name": self.order.name},
			fields=["file_name", "is_private"],
		)

	def complete(self):
		make_profile()
		self.sign("Customer")
		writeback.on_partial(self.name)
		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		writeback.on_complete(self.name)

	def test_sent_on_a_submitted_order(self):
		self.sent()
		self.assertEqual(
			self.order_values(), {"sign_status": "Sent", "sign_envelope": self.name, "docstatus": 1}
		)

	def test_partial_then_signed_with_pdf_and_comments(self):
		self.sent()
		make_profile()
		self.sign("Customer")
		writeback.on_partial(self.name)
		self.assertEqual(self.order_values().sign_status, "Partially Signed")
		self.assertTrue(any(f"{self.name} (Customer): signed by Ahmed Khan" in c for c in self.comments()))

		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		writeback.on_partial(self.name)  # a late recipient_signed job must not undo Signed
		writeback.on_complete(self.name)
		writeback.on_complete(self.name)  # a retried job adds nothing
		writeback.on_partial(self.name)
		self.assertEqual(self.order_values().sign_status, "Signed")
		self.assertEqual(self.attachments(), [{"file_name": f"{self.name}-signed.pdf", "is_private": 1}])
		comments = self.comments()
		self.assertEqual(len(comments), 3, comments)
		self.assertIn("the sealed PDF is attached", comments[-1])

	def test_declined_and_voided(self):
		self.sent()
		signing.decline(self.start(), "Price too high")
		writeback.on_declined(self.name)
		self.assertEqual(self.order_values().sign_status, "Declined")
		second = self.sent()
		envelope_service.void(second, "Wrong customer")
		writeback.on_voided(second)
		self.assertEqual(
			self.order_values(), {"sign_status": "Voided", "sign_envelope": second, "docstatus": 1}
		)

	def test_events_of_an_older_envelope_leave_the_status(self):
		first = self.sent()
		second = self.sent()
		writeback.on_declined(first)
		self.assertEqual(
			self.order_values(), {"sign_status": "Sent", "sign_envelope": second, "docstatus": 1}
		)

	def test_sender_with_sales_rights_writes_back(self):
		make_user("sales-signer@example.com", "Sign User", "Sales User")
		frappe.db.set_value("Sign Envelope", self.sent(), "sender", "sales-signer@example.com")
		self.complete_as("sales-signer@example.com")
		self.assertEqual(self.order_values().sign_status, "Signed")
		self.assertEqual(len(self.attachments()), 1)

	def complete_as(self, user: str):
		make_profile()
		self.sign("Customer")
		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		with self.as_user(user):
			writeback.on_partial(self.name)
			writeback.on_complete(self.name)

	def test_documents_without_the_fields_still_get_the_pdf(self):
		with patch("frappe_sign.services.writeback.has_sign_fields", return_value=False):
			self.sent()
			self.complete()
		self.assertEqual(len(self.attachments()), 1)
		self.assertFalse(self.order_values().sign_status)


if __name__ == "__main__":
	unittest.main()
