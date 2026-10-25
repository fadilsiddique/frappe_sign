"""ERPNext documents for tests/erpnext/. Every test there skips when ERPNext is not installed.

The test Company comes from tests/erpnext/bootstrap.py (before_tests). Documents made here live in
the test's transaction and roll back with it.
"""

import unittest

import frappe
from frappe.utils import add_days, nowdate

from frappe_sign.tests.base import SignTestCase


def erpnext_installed() -> bool:
	return "erpnext" in frappe.get_installed_apps()


class ERPNextTestCase(SignTestCase):
	@classmethod
	def setUpClass(cls):
		if not erpnext_installed():
			raise unittest.SkipTest("ERPNext is not installed")
		super().setUpClass()

	@property
	def company(self) -> str:
		return frappe.db.get_value("Company", {}, "name", order_by="creation asc")


def make_item(item_code: str = "FS-SERVICE", rate: float = 100.0):
	if frappe.db.exists("Item", item_code):
		return frappe.get_doc("Item", item_code)
	return frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code.replace("-", " ").title(),
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups",
			"stock_uom": "Nos",
			"is_stock_item": 0,
			"standard_rate": rate,
		}
	).insert()


def make_contact(first_name: str, email: str, mobile: str | None = None, links: list | None = None):
	contact = frappe.get_doc(
		{
			"doctype": "Contact",
			"first_name": first_name,
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"phone_nos": [{"phone": mobile, "is_primary_mobile_no": 1}] if mobile else [],
			"links": links or [],
		}
	)
	return contact.insert()


def make_customer(name: str = "Gulf Trading LLC", email: str | None = "ahmed@gulftrading.example"):
	if frappe.db.exists("Customer", name):
		return frappe.get_doc("Customer", name)
	customer = frappe.get_doc(
		{"doctype": "Customer", "customer_name": name, "customer_type": "Company"}
	).insert()
	if email:
		contact = make_contact(
			"Ahmed Khan",
			email,
			"+971500000001",
			links=[{"link_doctype": "Customer", "link_name": customer.name}],
		)
		contact.db_set("is_primary_contact", 1)
		customer.db_set("customer_primary_contact", contact.name)
	return customer


def make_supplier(name: str = "Desert Supplies LLC", email: str | None = "sara@desertsupplies.example"):
	if frappe.db.exists("Supplier", name):
		return frappe.get_doc("Supplier", name)
	supplier = frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": name,
			"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
		}
	).insert()
	if email:
		contact = make_contact(
			"Sara Ali",
			email,
			"+971500000002",
			links=[{"link_doctype": "Supplier", "link_name": supplier.name}],
		)
		contact.db_set("is_primary_contact", 1)
		supplier.db_set("supplier_primary_contact", contact.name)
	return supplier


def make_quotation(items: int = 3, customer: str | None = None, submit: bool = False, **overrides):
	customer = customer or make_customer().name
	codes = [make_item(f"FS-ITEM-{index:03d}", rate=10.0 + index).name for index in range(1, items + 1)]
	quotation = frappe.get_doc(
		{
			"doctype": "Quotation",
			"quotation_to": "Customer",
			"party_name": customer,
			"transaction_date": nowdate(),
			"valid_till": add_days(nowdate(), 30),
			"order_type": "Sales",
			"items": [
				{"item_code": code, "qty": 1 + index % 3, "rate": 10.0 + index}
				for index, code in enumerate(codes, start=1)
			],
			**overrides,
		}
	).insert()
	if submit:
		quotation.submit()
	return quotation
