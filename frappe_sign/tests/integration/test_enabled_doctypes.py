"""Sign Settings adds sign_status and sign_envelope to the DocTypes it enables (P2.3, DESIGN 2.5)."""

import unittest

import frappe

from frappe_sign.services import doctypes
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.doctypes import disable_doctypes, enable_doctypes
from frappe_sign.tests.factories import make_user


class TestEnabledDocTypes(SignTestCase):
	needs_email_account = False

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		enable_doctypes("ToDo")

	@classmethod
	def tearDownClass(cls):
		disable_doctypes("ToDo")
		super().tearDownClass()

	def test_enabled_doctype_gets_the_fields(self):
		meta = frappe.get_meta("ToDo")
		status, envelope = meta.get_field("sign_status"), meta.get_field("sign_envelope")
		self.assertEqual(
			(status.fieldtype, envelope.fieldtype, envelope.options), ("Select", "Link", "Sign Envelope")
		)
		self.assertIn("Partially Signed", status.options.split("\n"))
		for field in (status, envelope):
			self.assertEqual((field.allow_on_submit, field.read_only, field.no_copy), (1, 1, 1))
		self.assertEqual(status.in_list_view, 1)
		self.assertEqual(doctypes.enabled_doctypes(), ["ToDo"])

	def test_saving_again_adds_nothing(self):
		self.assertEqual(doctypes.add_custom_fields(["ToDo"]), [])

	def test_fields_stay_until_an_admin_removes_them(self):
		with self.assertRaises(frappe.ValidationError):
			doctypes.remove_custom_fields("ToDo")
		settings = frappe.get_single("Sign Settings")
		settings.enabled_doctypes = []
		settings.save()
		self.assertTrue(frappe.get_meta("ToDo").has_field("sign_status"))

	def test_only_a_system_manager_removes_fields(self):
		make_user("sign-manager-fields@example.com", "Sign Manager")
		with self.as_user("sign-manager-fields@example.com"), self.assertRaises(frappe.PermissionError):
			doctypes.remove_custom_fields("Note")

	def test_only_a_system_manager_enables_doctypes(self):
		make_user("sign-manager-fields@example.com", "Sign Manager")
		with self.as_user("sign-manager-fields@example.com"):
			settings = frappe.get_single("Sign Settings")
			settings.append("enabled_doctypes", {"reference_doctype": "Note"})
			with self.assertRaises(frappe.PermissionError):
				settings.save()


class TestRemoveFields(SignTestCase):
	needs_email_account = False

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		enable_doctypes("Note")
		disable_doctypes_rows("Note")

	@classmethod
	def tearDownClass(cls):
		disable_doctypes("Note")
		super().tearDownClass()

	def test_remove_deletes_the_fields(self):
		self.assertTrue(frappe.get_meta("Note").has_field("sign_status"))
		self.assertEqual(doctypes.remove_custom_fields("Note"), 2)
		frappe.clear_cache(doctype="Note")
		self.assertFalse(frappe.get_meta("Note").has_field("sign_status"))


def disable_doctypes_rows(*names: str) -> None:
	"""Take DocTypes off Sign Settings and keep their fields."""
	frappe.db.delete(
		"Sign Enabled DocType", {"parent": "Sign Settings", "reference_doctype": ["in", list(names)]}
	)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (tests own this setup)


if __name__ == "__main__":
	unittest.main()
