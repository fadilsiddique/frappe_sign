"""The send wizard's pickers: sendable DocTypes, documents and people (U.6)."""

import unittest

import frappe

from frappe_sign.api import staff
from frappe_sign.exceptions import FieldValidationError
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_user

HAS_ERPNEXT = "erpnext" in frappe.get_installed_apps()


def enable_doctype(doctype: str) -> None:
	"""The settings row alone: saving Sign Settings adds custom fields, a schema change that commits."""
	frappe.get_doc(
		{
			"doctype": "Sign Enabled DocType",
			"parent": "Sign Settings",
			"parenttype": "Sign Settings",
			"parentfield": "enabled_doctypes",
			"reference_doctype": doctype,
		}
	).db_insert()


class TestPickers(SignTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.refuse_commits()

	def test_only_enabled_doctypes_are_sendable_with_their_template_counts(self):
		frappe.db.delete("Sign Enabled DocType")
		enable_doctype("ToDo")
		self.assertEqual(staff.sendable_doctypes(), [{"doctype": "ToDo", "templates": 0}])

	def test_a_doctype_the_user_cannot_read_is_not_sendable(self):
		frappe.db.delete("Sign Enabled DocType")
		enable_doctype("Error Log")  # only System Managers read it
		make_user("picker.sign@example.com", "Sign User")
		with self.as_user("picker.sign@example.com"):
			self.assertEqual(staff.sendable_doctypes(), [])

	def test_documents_of_a_disabled_doctype_are_refused(self):
		frappe.db.delete("Sign Enabled DocType")
		self.assertRaises(FieldValidationError, staff.document_choices, "ToDo")

	def test_documents_match_the_number_and_come_newest_first(self):
		frappe.db.delete("Sign Enabled DocType")
		enable_doctype("ToDo")
		first = frappe.get_doc({"doctype": "ToDo", "description": "first"}).insert()
		second = frappe.get_doc({"doctype": "ToDo", "description": "second"}).insert()
		rows = staff.document_choices("ToDo")
		self.assertEqual([row["name"] for row in rows[:2]], [second.name, first.name])
		self.assertEqual([row["name"] for row in staff.document_choices("ToDo", first.name)], [first.name])
		self.assertTrue(rows[0]["date"])

	@unittest.skipUnless(HAS_ERPNEXT, "needs ERPNext")
	def test_a_quotation_shows_party_date_and_total(self):
		from frappe_sign.tests.erpnext.helpers import make_quotation

		frappe.db.delete("Sign Enabled DocType")
		enable_doctype("Quotation")
		quotation = make_quotation()
		row = next(r for r in staff.document_choices("Quotation") if r["name"] == quotation.name)
		self.assertEqual(row["party"], quotation.customer_name)
		self.assertEqual(row["total"], quotation.grand_total)
		self.assertEqual(row["currency"], quotation.currency)
		self.assertEqual(row["date"], str(quotation.transaction_date))
		by_party = staff.document_choices("Quotation", quotation.customer_name[:6])
		self.assertIn(quotation.name, [r["name"] for r in by_party])

	def test_people_come_from_contacts_and_users_once_each(self):
		frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Zainab",
				"last_name": "Pickerson",
				"email_ids": [{"email_id": "zainab.pickerson@example.com", "is_primary": 1}],
			}
		).insert()
		make_user("zainab.pickerson@example.com", "Sign User")
		found = staff.search_people("pickerson")
		emails = [person["email"] for person in found]
		self.assertEqual(emails.count("zainab.pickerson@example.com"), 1)
		self.assertTrue(all(person["full_name"] for person in found))

	def test_a_short_query_finds_nobody(self):
		self.assertEqual(staff.search_people("z"), [])
