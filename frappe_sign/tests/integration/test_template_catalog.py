"""The Templates page list and the Print Format picker of the template editor (U.7)."""

import frappe

from frappe_sign.api import staff
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.signing_helpers import make_draft, publish_template


class TestTemplateCatalog(SignTestCase):
	def setUp(self):
		super().setUp()
		self.refuse_commits()

	def test_a_template_lists_with_the_time_a_request_last_used_it(self):
		version = publish_template()
		template = frappe.db.get_value("Sign Template Version", version, "template")
		unused = next(row for row in staff.list_templates() if row["name"] == template)
		self.assertIsNone(unused["last_used"])
		make_draft(version)
		used = next(row for row in staff.list_templates() if row["name"] == template)
		self.assertIsNotNone(used["last_used"])

	def test_print_formats_say_whether_they_place_signature_fields(self):
		for name, html in (
			("U7 Signed", "{{ sign_field('Customer', 'signature') }}"),
			("U7 Plain", "<p>Hello</p>"),
		):
			frappe.get_doc(
				{
					"doctype": "Print Format",
					"name": name,
					"doc_type": "ToDo",
					"custom_format": 1,
					"print_format_type": "Jinja",
					"html": html,
				}
			).insert()
		rows = {row["name"]: row["has_sign_fields"] for row in staff.template_print_formats("ToDo")}
		self.assertTrue(rows["U7 Signed"])
		self.assertFalse(rows["U7 Plain"])

	def test_settable_fields_leave_out_layout_read_only_and_table_fields(self):
		names = {row["fieldname"] for row in staff.template_doctype_fields("ToDo")}
		self.assertIn("description", names)
		self.assertNotIn("creation", names)
