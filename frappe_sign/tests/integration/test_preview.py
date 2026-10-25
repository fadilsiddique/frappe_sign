"""Send wizard preview of a Print Format source: anchors, cache, prefill (P2.9)."""

import unittest
from unittest.mock import patch

import frappe

from frappe_sign.services import preview
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_user
from frappe_sign.tests.integration.test_anchored_send import HTML, POSITIONS
from frappe_sign.tests.integration.test_resolvers import publish, role
from frappe_sign.tests.printing import make_print_format
from frappe_sign.tests.unit.test_anchors import marker_pdf


class TestPreview(SignTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Preview me"}).insert()
		self.print_format = make_print_format("ToDo", HTML, "chrome")
		self.pdf = marker_pdf([(tag, *place) for tag, place in POSITIONS.items()])

	def preview(self):
		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=self.pdf) as chrome:
			result = preview.preview_source("ToDo", self.todo.name, self.print_format.name)
		return result, chrome

	def test_anchors_and_metrics(self):
		result, _chrome = self.preview()
		self.assertEqual((result["generator"], result["generator_tested"]), ("chrome", True))
		self.assertEqual({anchor["tag"] for anchor in result["anchors"]}, set(POSITIONS))
		signature = next(a for a in result["anchors"] if a["tag"] == "[[fs:Customer:signature:1]]")
		self.assertAlmostEqual(signature["w"], 60 * 72 / 25.4 / 595, 3)
		self.assertEqual(len(result["metrics"]), 1)
		self.assertTrue(preview.preview_pdf(result["key"]).startswith(b"%PDF"))

	def test_second_preview_comes_from_the_cache(self):
		first, _chrome = self.preview()
		second, chrome = self.preview()
		self.assertEqual(first["key"], second["key"])
		chrome.assert_not_called()

	def test_pdf_only_for_the_user_who_rendered_it(self):
		result, _chrome = self.preview()
		make_user("someone-else@example.com", "Sign User")
		with self.as_user("someone-else@example.com"), self.assertRaises(frappe.ValidationError):
			preview.preview_pdf(result["key"])

	def test_prefill_values(self):
		template = publish(
			[role("Owner", "Ask at Send")],
			print_format=self.print_format.name,
			fields=[
				{
					"field_key": "description",
					"role_label": "Owner",
					"field_type": "Text",
					"page": 1,
					"x": 0.1,
					"y": 0.1,
					"w": 0.3,
					"h": 0.05,
					"read_only": 1,
					"prefill_path": "description",
				},
				{
					"field_key": "shout",
					"role_label": "Owner",
					"field_type": "Text",
					"page": 1,
					"x": 0.1,
					"y": 0.2,
					"w": 0.3,
					"h": 0.05,
					"prefill_path": "{{ doc.description | upper }}",
				},
			],
		)
		values = {
			row["field_key"]: row["value"]
			for row in preview.preview_prefill(template, "ToDo", self.todo.name)
		}
		self.assertEqual(values, {"description": "Preview me", "shout": "PREVIEW ME"})


if __name__ == "__main__":
	unittest.main()
