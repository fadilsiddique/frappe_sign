"""Send a Quotation for signature from Desk: one-click send and bulk send (P2.5, DESIGN 4.1)."""

import unittest
from unittest.mock import patch

import frappe

from frappe_sign.jobs import bulk
from frappe_sign.services import documents
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services.resolvers import resolve_recipients
from frappe_sign.tests.doctypes import disable_doctypes, enable_doctypes
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_customer, make_quotation
from frappe_sign.tests.erpnext.quotation import default_template_for, publish_quotation_template
from frappe_sign.tests.integration.test_sealing import no_commits
from frappe_sign.tests.printing import make_print_format
from frappe_sign.utils.boot import desk_boot


class TestSendFromDocument(ERPNextTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		enable_doctypes("Quotation")

	@classmethod
	def tearDownClass(cls):
		disable_doctypes("Quotation")
		super().tearDownClass()

	def setUp(self):
		super().setUp()
		self.quotation = make_quotation(items=3, submit=True)
		self.template = publish_quotation_template()

	def test_templates_for_the_doctype_default_first(self):
		other = publish_quotation_template(title="Another")
		default_template_for("Quotation", other)
		rows = documents.templates_for("Quotation")
		self.assertEqual([row.name for row in rows][:1], [other])
		self.assertEqual({row.name for row in rows}, {self.template, other})
		self.assertEqual(documents.templates_for("Sales Order"), [])

	def test_send_creates_and_queues_the_envelope(self):
		rows = resolve_recipients(self.template, "Quotation", self.quotation.name)
		with self.capture_enqueue() as calls:
			name = documents.send_from_document(
				"Quotation", self.quotation.name, self.template, rows, message="Please sign", letter_head=None
			)
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertEqual((doc.status, doc.send_state), ("Draft", "Queued"))
		self.assertEqual((doc.reference_doctype, doc.reference_name), ("Quotation", self.quotation.name))
		self.assertEqual((doc.party_type, doc.party), ("Customer", self.quotation.party_name))
		self.assertEqual(doc.company, self.quotation.company)
		self.assertEqual(doc.message, "Please sign")
		self.assertEqual(doc.recipients[0].email, "ahmed@gulftrading.example")
		self.assertEqual([call["method"] for call in calls], ["frappe_sign.jobs.render.run"])

	def test_print_view_choice_overrides_the_template_format(self):
		other = make_print_format(
			"Quotation", "<p>{{ doc.name }}</p>", "chrome", name="Frappe Sign Test Other"
		).name
		rows = resolve_recipients(self.template, "Quotation", self.quotation.name)
		with self.capture_enqueue():
			name = documents.send_from_document(
				"Quotation", self.quotation.name, self.template, rows, print_format=other
			)
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "print_format"), other)

	def test_template_for_another_doctype_is_refused(self):
		template = frappe.get_doc("Sign Template", self.template)
		template.db_set("reference_doctype", "Sales Order")
		with self.assertRaises(frappe.ValidationError):
			documents.send_from_document("Quotation", self.quotation.name, self.template, [])

	def test_bulk_send_queues_one_job(self):
		with self.capture_enqueue() as calls:
			result = documents.queue_bulk_send("Quotation", [self.quotation.name] * 2, self.template)
		self.assertEqual(result["queued"], 1)
		self.assertEqual(calls[0]["method"], "frappe_sign.jobs.bulk.run")
		self.assertEqual(calls[0]["queue"], "long")

	def test_bulk_job_sends_what_resolves_and_reports_the_rest(self):
		silent = make_quotation(
			items=1, customer=make_customer("Silent Trading LLC", email=None).name, submit=True
		)
		with self.capture_enqueue():
			run = documents.queue_bulk_send("Quotation", [self.quotation.name, silent.name], self.template)[
				"run"
			]
		with no_commits(), patch("frappe.enqueue"):
			bulk.run(run)
		sent = frappe.get_all("Sign Envelope", filters={"reference_name": self.quotation.name}, pluck="name")
		self.assertEqual(len(sent), 1)
		self.assertFalse(frappe.db.exists("Sign Envelope", {"reference_name": silent.name}))
		self.assertTrue(
			frappe.db.exists("Error Log", {"reference_name": silent.name, "method": "Frappe Sign: bulk send"})
		)
		note = frappe.get_last_doc("Notification Log", filters={"document_type": "Sign Bulk Run"})
		self.assertIn("1 of 2", note.subject)
		self.assertIn(silent.name, note.subject)

	def test_desk_boot_lists_enabled_doctypes(self):
		bootinfo = frappe._dict()
		desk_boot(bootinfo)
		self.assertIn("Quotation", bootinfo.frappe_sign["enabled_doctypes"])
		self.assertTrue(bootinfo.frappe_sign["can_send"])

	def test_send_then_render_places_the_anchor_fields(self):
		rows = resolve_recipients(self.template, "Quotation", self.quotation.name)
		with self.capture_enqueue():
			name = documents.send_from_document("Quotation", self.quotation.name, self.template, rows)
		with patch("frappe.utils.pdf.get_chrome_pdf", side_effect=fake_chrome):
			envelope_service.render_and_send(name)
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertEqual(doc.status, "Sent")
		self.assertEqual(
			sorted(field.field_key for field in doc.fields),
			["company_signature_1", "customer_date_signed_1", "customer_signature_1"],
		)


def fake_chrome(print_format, html, options, output, pdf_generator=None):
	"""A PDF with the markers the Quotation template declares, without Chromium."""
	from frappe_sign.tests.unit.test_anchors import marker_pdf

	return marker_pdf(
		[
			("[[fs:Customer:signature:1]]", 60, 600),
			("[[fs:Customer:date_signed:1]]", 60, 680),
			("[[fs:Company:signature:1]]", 320, 600),
		]
	)


if __name__ == "__main__":
	unittest.main()
