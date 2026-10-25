"""Signatures on the Customer, Supplier and Employee dashboards (P2.10, DESIGN 4.8)."""

import unittest

import frappe
from frappe.desk.notifications import get_open_count

from frappe_sign.erpnext import dashboards
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_customer, make_supplier
from frappe_sign.tests.signing_helpers import make_draft


def signature_items(meta_doctype: str) -> list[str]:
	data = frappe.get_meta(meta_doctype).get_dashboard_data()
	return [
		item for group in data.transactions if group.get("label") == "Signatures" for item in group["items"]
	]


class TestPartyDashboards(ERPNextTestCase):
	def test_groups_on_each_party(self):
		for doctype in ("Customer", "Supplier", "Employee"):
			with self.subTest(doctype=doctype):
				self.assertEqual(signature_items(doctype), ["Sign Envelope"])

	def test_existing_party_links_are_kept(self):
		data = dashboards.customer(
			{"fieldname": "customer", "dynamic_links": {"party": ["Customer", "party_type"]}}
		)
		self.assertEqual(data.dynamic_links["party"], ["Customer", "party_type"])
		data = dashboards.employee({})
		self.assertEqual(
			(data.fieldname, data.non_standard_fieldnames["Sign Envelope"]), ("employee", "party")
		)
		twice = dashboards.customer(dashboards.customer({}))
		self.assertEqual(len([g for g in twice.transactions if g["label"] == "Signatures"]), 1)

	def test_counts_only_the_partys_envelopes(self):
		customer = make_customer()
		supplier = (
			make_supplier(name=customer.name, email=None)
			if not frappe.db.exists("Supplier", customer.name)
			else None
		)
		make_draft(party_type="Customer", party=customer.name)
		if supplier:
			make_draft(party_type="Supplier", party=supplier.name)
		counts = get_open_count("Customer", customer.name, items=["Sign Envelope"])
		count = next(
			row for row in counts["count"]["external_links_found"] if row["doctype"] == "Sign Envelope"
		)
		self.assertEqual(count["count"], 1)


if __name__ == "__main__":
	unittest.main()
