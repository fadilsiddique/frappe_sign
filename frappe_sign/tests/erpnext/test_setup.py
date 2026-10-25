"""ERPNext setup: company fields become Link Company (P2.3, DESIGN 2.1), and enabled ERPNext
DocTypes get fields that change after submit."""

import unittest

import frappe

from frappe_sign.erpnext import setup
from frappe_sign.tests.doctypes import disable_doctypes, enable_doctypes
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_quotation
from frappe_sign.tests.factories import make_template


class TestLinkCompany(ERPNextTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.addCleanup(clear_company_caches)

	def test_company_fields_link_to_company(self):
		self.assertTrue(setup.link_company_fields())
		self.assertTrue(setup.is_linked())
		for doctype, fieldname in setup.COMPANY_FIELDS:
			field = frappe.get_meta(doctype).get_field(fieldname)
			self.assertEqual((field.fieldtype, field.options), ("Link", "Company"), doctype)

	def test_link_validates_the_company(self):
		with self.assertRaises(frappe.LinkValidationError):
			make_template(company="No Such Company LLC")
		self.assertEqual(make_template(company=self.company).company, self.company)

	def test_unknown_company_values_block_the_switch(self):
		setup.unlink_company_fields()
		self.assertFalse(setup.is_linked())
		make_template(company="No Such Company LLC")
		self.assertFalse(setup.link_company_fields())
		self.assertFalse(setup.is_linked())
		log = frappe.get_last_doc("Error Log", filters={"method": "Frappe Sign: Link Company"})
		self.assertIn("Sign Template: No Such Company LLC", log.error)

	def test_uninstalling_erpnext_unlinks(self):
		setup.before_app_uninstall("erpnext")
		self.assertFalse(setup.is_linked())
		self.assertEqual(frappe.get_meta("Sign Profile").get_field("company").fieldtype, "Data")
		setup.after_app_install("erpnext")
		self.assertTrue(setup.is_linked())


def clear_company_caches():
	for doctype, _fieldname in setup.COMPANY_FIELDS:
		frappe.clear_cache(doctype=doctype)


class TestSubmittedQuotationFields(ERPNextTestCase):
	needs_email_account = False

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		enable_doctypes("Quotation")

	@classmethod
	def tearDownClass(cls):
		disable_doctypes("Quotation")
		super().tearDownClass()

	def test_status_changes_after_submit(self):
		quotation = make_quotation(items=1, submit=True)
		quotation.sign_status = "Sent"
		quotation.save()
		self.assertEqual(frappe.db.get_value("Quotation", quotation.name, "sign_status"), "Sent")

	def test_fields_are_not_copied_to_an_amendment(self):
		meta = frappe.get_meta("Quotation")
		self.assertEqual(meta.get_field("sign_status").no_copy, 1)
		self.assertEqual(meta.get_field("sign_envelope").no_copy, 1)


if __name__ == "__main__":
	unittest.main()
