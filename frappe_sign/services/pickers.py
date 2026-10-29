"""Pickers of the send wizard (UX_PLAN "New request", U.6): the DocTypes a user may send, the
documents of one DocType, and people to choose from. All reads go through frappe.get_list, so
they follow the user's permissions.

A document row is described from the fields its DocType has: the party (customer, supplier,
employee or title), the date and the total. A DocType without them just shows the number.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import doctypes

PARTY_FIELDS = ("customer_name", "supplier_name", "employee_name", "party_name", "title")
DATE_FIELDS = ("transaction_date", "posting_date", "date_of_joining", "creation")
TOTAL_FIELDS = ("grand_total", "rounded_total")
LIMIT = 20


def sendable_doctypes() -> list[dict[str, Any]]:
	"""The enabled DocTypes the user may read, each with the number of published templates."""
	rows = []
	for doctype in doctypes.enabled_doctypes():
		if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
			continue
		templates = frappe.db.count(
			"Sign Template",
			{"reference_doctype": doctype, "is_active": 1, "published_version": ["is", "set"]},
		)
		rows.append({"doctype": doctype, "templates": templates})
	return rows


def first_field(meta: Any, candidates: tuple[str, ...]) -> str | None:
	return next((field for field in candidates if meta.has_field(field) or field == "creation"), None)


def document_choices(doctype: str, query: str = "", limit: int = LIMIT) -> list[dict[str, Any]]:
	"""Documents of an enabled DocType, newest first, matching the query in the number or the
	party. Cancelled documents are left out."""
	if doctype not in doctypes.enabled_doctypes():
		throw(FieldValidationError, _("{0} is not enabled for signing.").format(_(doctype)))
	frappe.has_permission(doctype, "read", throw=True)
	meta = frappe.get_meta(doctype)
	party = first_field(meta, PARTY_FIELDS)
	date = first_field(meta, DATE_FIELDS)
	total = first_field(meta, TOTAL_FIELDS)
	currency = "currency" if total and meta.has_field("currency") else None
	fields = ["name", *(field for field in (party, date, total, currency) if field)]
	query = query.strip()
	or_filters = {"name": ["like", f"%{query}%"]}
	if query and party:
		or_filters[party] = ["like", f"%{query}%"]
	rows = frappe.get_list(
		doctype,
		fields=fields,
		filters={"docstatus": ["<", 2]} if meta.is_submittable else None,
		or_filters=or_filters if query else None,
		order_by="modified desc",
		limit=min(max(int(limit), 1), 50),
	)
	return [
		{
			"name": row.name,
			"party": cstr(row.get(party)) if party else "",
			"date": cstr(row.get(date))[:10] if date and row.get(date) else "",
			"total": row.get(total) if total else None,
			"currency": cstr(row.get(currency)) if currency else "",
		}
		for row in rows
	]


def search_people(query: str, limit: int = 8) -> list[dict[str, str]]:
	"""Contacts and users with an email address, for the people step. A user who cannot read
	Contacts or Users gets none of them, not an error."""
	query = query.strip()
	if len(query) < 2:
		return []
	found: list[dict[str, str]] = []
	if frappe.has_permission("Contact", "read"):
		contacts = frappe.get_list(
			"Contact",
			fields=["name", "first_name", "last_name", "email_id"],
			filters={"email_id": ["is", "set"]},
			or_filters={
				"first_name": ["like", f"%{query}%"],
				"last_name": ["like", f"%{query}%"],
				"email_id": ["like", f"%{query}%"],
			},
			limit=limit,
		)
		found += [
			{
				"full_name": " ".join(part for part in (row.first_name, row.last_name) if part),
				"email": row.email_id,
				"source": "Contact",
			}
			for row in contacts
		]
	if frappe.has_permission("User", "read"):
		users = frappe.get_list(
			"User",
			fields=["full_name", "email"],
			filters={"enabled": 1, "user_type": "System User"},
			or_filters={"full_name": ["like", f"%{query}%"], "email": ["like", f"%{query}%"]},
			limit=limit,
		)
		found += [{"full_name": row.full_name, "email": row.email, "source": "User"} for row in users]
	seen: set[str] = set()
	unique = []
	for person in found:
		key = person["email"].lower()
		if key not in seen and person["full_name"]:
			seen.add(key)
			unique.append(person)
	return unique[:limit]
