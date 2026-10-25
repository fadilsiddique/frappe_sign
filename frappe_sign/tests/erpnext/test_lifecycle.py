"""Lifecycle sync on a submitted Quotation (P2.8, DESIGN 4.7): cancel and amend void what is open."""

import unittest

import frappe

from frappe_sign.jobs import triggers as trigger_jobs
from frappe_sign.services import gate
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_quotation
from frappe_sign.tests.integration.test_dispatcher import ours
from frappe_sign.tests.integration.test_sealing import no_commits
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, send_now


class TestQuotationLifecycle(ERPNextTestCase):
	def setUp(self):
		super().setUp()
		gate.clear()
		self.addCleanup(gate.clear)
		self.quotation = make_quotation(items=1, submit=True)
		draft = make_draft(reference_doctype="Quotation", reference_name=self.quotation.name)
		with capture_tokens():
			send_now(draft.name)
		self.envelope = draft.name

	def run_lifecycle(self, calls):
		for call in ours(calls):
			with no_commits():
				trigger_jobs.lifecycle(call["envelope"], call["action"], call["reason"])

	def test_cancel_voids_the_open_envelope(self):
		with self.capture_enqueue() as calls:
			self.quotation.cancel()
		self.run_lifecycle(calls)
		doc = frappe.get_doc("Sign Envelope", self.envelope)
		self.assertEqual(doc.status, "Voided")
		self.assertIn("cancelled", doc.void_reason)

	def test_amendment_voids_what_is_still_open(self):
		with self.capture_enqueue():
			self.quotation.cancel()  # its void job has not run yet
		amended = frappe.copy_doc(self.quotation)
		amended.amended_from = self.quotation.name
		amended.docstatus = 0
		with self.capture_enqueue() as calls:
			amended.insert()
		self.run_lifecycle(calls)
		doc = frappe.get_doc("Sign Envelope", self.envelope)
		self.assertEqual(doc.status, "Voided")
		self.assertIn(amended.name, doc.void_reason)

	def test_update_after_submit_flags_source_changed(self):
		with self.capture_enqueue() as calls:
			self.quotation.reload()
			field = next(
				df.fieldname
				for df in self.quotation.meta.fields
				if df.allow_on_submit and df.fieldtype in ("Data", "Small Text", "Text", "Text Editor")
			)
			self.quotation.set(field, "Changed after submit")
			self.quotation.save()
		self.run_lifecycle(calls)
		self.assertEqual(frappe.db.get_value("Sign Envelope", self.envelope, "source_changed"), 1)


if __name__ == "__main__":
	unittest.main()
