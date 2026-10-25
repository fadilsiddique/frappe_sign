"""ERPNext resolvers (P2.4, DESIGN 4.3): the right signer per DocType, and "unresolved" instead of
an error when data is missing."""

import unittest

import frappe
from frappe.utils import add_days, nowdate

from frappe_sign.erpnext import resolvers as erpnext_resolvers
from frappe_sign.services import resolvers
from frappe_sign.tests.erpnext.helpers import (
	ERPNextTestCase,
	make_contact,
	make_customer,
	make_quotation,
	make_supplier,
)
from frappe_sign.tests.integration.test_resolvers import publish, role


class TestERPNextResolvers(ERPNextTestCase):
	needs_email_account = False

	def test_every_field_read_exists_in_the_doctype(self):
		# The floor CI cells run this against ERPNext v16.0.0.
		for doctype, fields in erpnext_resolvers.FIELDS.items():
			if not frappe.db.exists("DocType", doctype):
				continue  # Job Offer and Job Applicant come with HRMS
			meta = frappe.get_meta(doctype)
			missing = [field for field in fields if not meta.has_field(field)]
			self.assertEqual(missing, [], doctype)

	def test_quotation_uses_its_contact_person(self):
		quotation = make_quotation(items=1)
		[found] = resolvers.suggest("Quotation", quotation.name)
		self.assertEqual(found["party_type"], "Customer")
		self.assertEqual(found["party"], quotation.party_name)
		self.assertEqual(found["email"], "ahmed@gulftrading.example")
		self.assertEqual(found["full_name"], "Ahmed Khan")

	def test_quotation_falls_back_to_contact_email(self):
		quotation = make_quotation(items=1)
		quotation.db_set({"contact_person": None, "contact_email": "buyer@gulftrading.example"})
		[found] = resolvers.suggest("Quotation", quotation.name)
		self.assertEqual(found["email"], "buyer@gulftrading.example")

	def test_quotation_to_a_lead(self):
		lead = frappe.get_doc(
			{
				"doctype": "Lead",
				"first_name": "Omar",
				"lead_name": "Omar Saeed",
				"email_id": "omar@lead.example",
			}
		).insert()
		doc = frappe.get_doc({"doctype": "Quotation", "quotation_to": "Lead", "party_name": lead.name})
		[found] = resolvers.suggestions_of(doc)
		self.assertEqual((found["party_type"], found["email"]), ("Lead", "omar@lead.example"))

	def test_customer_without_contact_is_unresolved(self):
		customer = make_customer("Silent Trading LLC", email=None)
		doc = frappe.get_doc(
			{"doctype": "Sales Order", "customer": customer.name, "customer_name": customer.name}
		)
		[found] = resolvers.suggestions_of(doc)
		self.assertEqual(
			(found["party"], found["email"], found["full_name"]), (customer.name, None, customer.name)
		)

	def test_sales_order_and_purchase_order(self):
		customer, supplier = make_customer(), make_supplier()
		[sales] = resolvers.suggestions_of(
			frappe.get_doc({"doctype": "Sales Order", "customer": customer.name})
		)
		[purchase] = resolvers.suggestions_of(
			frappe.get_doc({"doctype": "Purchase Order", "supplier": supplier.name})
		)
		self.assertEqual(sales["email"], "ahmed@gulftrading.example")
		self.assertEqual(
			(purchase["party_type"], purchase["email"]), ("Supplier", "sara@desertsupplies.example")
		)

	def test_contract_party_contact(self):
		customer = make_customer()
		doc = frappe.get_doc({"doctype": "Contract", "party_type": "Customer", "party_name": customer.name})
		[found] = resolvers.suggestions_of(doc)
		self.assertEqual((found["party"], found["email"]), (customer.name, "ahmed@gulftrading.example"))

	def test_primary_contact_found_through_links(self):
		customer = make_customer("Linked Trading LLC", email=None)
		make_contact(
			"Mona Salem",
			"mona@linked.example",
			links=[{"link_doctype": "Customer", "link_name": customer.name}],
		)
		[found] = resolvers.suggest("Customer", customer.name)
		self.assertEqual(found["email"], "mona@linked.example")

	def test_employee_and_employee_linked_documents(self):
		employee = make_employee()
		[found] = resolvers.suggest("Employee", employee.name)
		self.assertEqual((found["email"], found["mobile"]), ("layla@company.example", "+971500000009"))
		driver = frappe.get_doc({"doctype": "Driver", "full_name": "Layla Driver", "employee": employee.name})
		[linked] = resolvers.suggestions_of(driver)
		self.assertEqual(linked["party"], employee.name)

	def test_job_offer(self):
		offer = frappe._dict(
			doctype="Job Offer",
			job_applicant="HR-APP-0001",
			applicant_name="Sami",
			applicant_email="sami@example.com",
		)
		[found] = erpnext_resolvers.job_offer(offer)
		self.assertEqual((found["party_type"], found["email"]), ("Job Applicant", "sami@example.com"))

	def test_missing_fields_give_unresolved_not_errors(self):
		for resolver in (
			erpnext_resolvers.quotation,
			erpnext_resolvers.sales_order,
			erpnext_resolvers.purchase_order,
			erpnext_resolvers.contract,
			erpnext_resolvers.employee,
			erpnext_resolvers.job_offer,
			erpnext_resolvers.lead,
		):
			with self.subTest(resolver=resolver.__name__):
				[found] = resolver(frappe._dict(doctype="Unknown", name=None))
				self.assertIsNone(resolvers.clean(found)["email"])

	def test_template_roles_for_a_quotation(self):
		quotation = make_quotation(items=1)
		template = publish(
			[role("Customer", "Party Contact"), role("Company", "Fixed User", fixed_user="Administrator")]
		)
		rows = resolvers.resolve_recipients(template, "Quotation", quotation.name)
		self.assertEqual(rows[0]["email"], "ahmed@gulftrading.example")
		self.assertEqual(resolvers.primary_party(rows), ("Customer", quotation.party_name))


def make_employee():
	return frappe.get_doc(
		{
			"doctype": "Employee",
			"first_name": "Layla",
			"last_name": "Hassan",
			"gender": frappe.db.get_value("Gender", {}, "name"),
			"date_of_birth": "1990-01-01",
			"date_of_joining": add_days(nowdate(), -30),
			"company": frappe.db.get_value("Company", {}, "name"),
			"company_email": "layla@company.example",
			"cell_number": "+971500000009",
		}
	).insert()


if __name__ == "__main__":
	unittest.main()
