"""Signatures group on Customer, Supplier and Employee dashboards (DESIGN 4.8).

Sign Envelope links to the party through `party_type` and `party`. ERPNext's Customer and Supplier
dashboards already filter "party" by party_type; the Employee has no dashboard in ERPNext v16.0.0
(HRMS adds one), so each override only adds what is missing.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _


def customer(data: dict[str, Any] | None = None) -> dict[str, Any]:
	return add_signatures(data, "Customer")


def supplier(data: dict[str, Any] | None = None) -> dict[str, Any]:
	return add_signatures(data, "Supplier")


def employee(data: dict[str, Any] | None = None) -> dict[str, Any]:
	return add_signatures(data, "Employee")


def add_signatures(data: dict[str, Any] | None, party_type: str) -> dict[str, Any]:
	data = frappe._dict(data or {})
	data.setdefault("fieldname", frappe.scrub(party_type))
	data.setdefault("non_standard_fieldnames", {})["Sign Envelope"] = "party"
	data.setdefault("dynamic_links", {}).setdefault("party", [party_type, "party_type"])
	transactions = data.setdefault("transactions", [])
	if not any("Sign Envelope" in group.get("items", []) for group in transactions):
		transactions.append({"label": _("Signatures"), "items": ["Sign Envelope"]})
	return data
