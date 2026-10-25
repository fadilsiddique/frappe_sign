"""Envelopes rendered from a Print Format of their reference document (D5, P2.1)."""

import unittest
from unittest.mock import patch

import frappe

from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import template as template_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf
from frappe_sign.tests.integration.test_source import HTML, fake_generators
from frappe_sign.tests.printing import make_print_format
from frappe_sign.tests.signing_helpers import CUSTOMER, send_now

CUSTOMER_ROLE = {"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send"}


def publish_print_template(print_format: str, **extra) -> str:
	template = template_service.create_template(
		{
			"title": "To do sign-off",
			"source_type": "Print Format",
			"reference_doctype": "ToDo",
			"print_format": print_format,
			"roles": [CUSTOMER_ROLE],
			"fields": [
				{
					"field_key": "customer_signature",
					"role_label": "Customer",
					"field_type": "Signature",
					"page": 1,
					"x": 0.1,
					"y": 0.8,
					"w": 0.3,
					"h": 0.08,
				}
			],
			**extra,
		}
	)
	return template_service.publish(template.name).name


class TestPrintSource(SignTestCase):
	def setUp(self):
		super().setUp()
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Sign this to do"}).insert()
		self.print_format = make_print_format("ToDo", HTML, "chrome")

	def draft(self, **payload):
		return envelope_service.create_draft(
			{
				"template_version": publish_print_template(self.print_format.name),
				"reference_doctype": "ToDo",
				"reference_name": self.todo.name,
				"recipients": [CUSTOMER],
				**payload,
			}
		)

	def test_draft_copies_the_print_format_from_the_template(self):
		doc = self.draft()
		self.assertEqual(doc.print_format, self.print_format.name)

	def test_send_renders_the_reference_document(self):
		doc = self.draft()
		with fake_generators() as calls:
			send_now(doc.name)
		doc.reload()
		self.assertEqual(calls, ["chrome"])
		self.assertEqual(doc.status, "Sent")
		self.assertTrue(doc.original_file)

	def test_sending_needs_the_reference_document(self):
		doc = self.draft(reference_name=None)
		with self.assertRaises(frappe.ValidationError):
			envelope_service.send(doc.name)

	def test_render_failure_fails_the_send(self):
		doc = self.draft()
		with patch("frappe.utils.pdf.get_chrome_pdf", side_effect=RuntimeError("Chromium crashed")):
			with patch("frappe.enqueue"):
				envelope_service.send(doc.name)
			with self.assertRaises(envelope_service.SendFailed) as raised:
				envelope_service.render_and_send(doc.name)
		self.assertIn("Chromium crashed", str(raised.exception))

	def test_ad_hoc_envelope_with_a_print_format(self):
		doc = envelope_service.create_draft(
			{
				"reference_doctype": "ToDo",
				"reference_name": self.todo.name,
				"print_format": self.print_format.name,
				"recipients": [CUSTOMER],
			}
		)
		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=fixture_pdf()):
			send_now(doc.name)
		self.assertEqual(frappe.db.get_value("Sign Envelope", doc.name, "status"), "Sent")


if __name__ == "__main__":
	unittest.main()
