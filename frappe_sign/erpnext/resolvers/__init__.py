"""Recipient resolvers per ERPNext DocType, registered through frappe_sign_resolvers (DESIGN 4.3).

Every field read here is listed in FIELDS and was checked against the ERPNext v16.0.0 DocType
JSON (Job Offer and Job Applicant against HRMS v16.0.0); tests/erpnext/test_resolvers.py checks it
against the installed meta, which is v16.0.0 in the floor CI cells. Fields are read with doc.get()
and records with frappe.db, so a missing field or record gives no suggestion, never an error.
"""

from __future__ import annotations

from typing import Any

import frappe

from frappe_sign.services.resolvers import Suggestion, contact_details, linked, user_suggestion

FIELDS = {
	"Quotation": (
		"quotation_to",
		"party_name",
		"customer_name",
		"contact_person",
		"contact_email",
		"contact_mobile",
	),
	"Sales Order": ("customer", "customer_name", "contact_person", "contact_email", "contact_mobile"),
	"Purchase Order": ("supplier", "supplier_name", "contact_person", "contact_email", "contact_mobile"),
	"Contract": ("party_type", "party_name", "party_user"),
	"Customer": ("customer_name", "customer_primary_contact"),
	"Supplier": ("supplier_name", "supplier_primary_contact"),
	"Lead": ("lead_name", "email_id", "mobile_no"),
	"Employee": (
		"employee_name",
		"prefered_email",
		"company_email",
		"personal_email",
		"user_id",
		"cell_number",
	),
	"Job Offer": ("job_applicant", "applicant_name", "applicant_email"),
	"Job Applicant": ("applicant_name", "email_id"),
}


def quotation(doc: Any) -> list[Suggestion]:
	return [party_document(doc, doc.get("quotation_to"), doc.get("party_name"), doc.get("customer_name"))]


def sales_order(doc: Any) -> list[Suggestion]:
	return [party_document(doc, "Customer", doc.get("customer"), doc.get("customer_name"))]


def purchase_order(doc: Any) -> list[Suggestion]:
	return [party_document(doc, "Supplier", doc.get("supplier"), doc.get("supplier_name"))]


def party_document(doc: Any, party_type: str | None, party: str | None, party_name: str | None) -> Suggestion:
	"""A selling or buying document: its contact_person, else its contact_email and contact_mobile,
	else the party's primary contact."""
	found: Suggestion = {"party_type": party_type, "party": party}
	details = contact_details(doc.get("contact_person"))
	if details:
		return {**found, **details, "full_name": details.get("full_name") or party_name}
	if doc.get("contact_email"):
		return {
			**found,
			"full_name": party_name or party,
			"email": doc.get("contact_email"),
			"mobile": doc.get("contact_mobile"),
		}
	return {**found, **(linked(party_type, party) or {"full_name": party_name or party})}


def contract(doc: Any) -> list[Suggestion]:
	party_type, party = doc.get("party_type"), doc.get("party_name")
	found: Suggestion = {"party_type": party_type, "party": party, **(linked(party_type, party) or {})}
	if not found.get("email") and doc.get("party_user"):
		found |= user_suggestion(doc.get("party_user"))
	return [found]


def customer(doc: Any) -> list[Suggestion]:
	return [party_contact(doc, doc.get("customer_primary_contact"), doc.get("customer_name"))]


def supplier(doc: Any) -> list[Suggestion]:
	return [party_contact(doc, doc.get("supplier_primary_contact"), doc.get("supplier_name"))]


def party_contact(doc: Any, primary: str | None, name: str | None) -> Suggestion:
	"""The party's primary contact: the one set on the party, else a linked Contact marked primary."""
	found: Suggestion = {"party_type": doc.doctype, "party": doc.name, "full_name": name or doc.name}
	details = contact_details(primary or primary_linked_contact(doc.doctype, doc.name))
	return {**found, **details} if details else found


def primary_linked_contact(doctype: str, name: str) -> str | None:
	contacts = frappe.get_all(
		"Dynamic Link",
		filters={"parenttype": "Contact", "link_doctype": doctype, "link_name": name},
		pluck="parent",
	)
	if not contacts:
		return None
	primary = frappe.get_all(
		"Contact", filters={"name": ["in", contacts], "is_primary_contact": 1}, pluck="name", limit=1
	)
	return primary[0] if primary else contacts[0]


def lead(doc: Any) -> list[Suggestion]:
	return [
		{
			"party_type": "Lead",
			"party": doc.name,
			"full_name": doc.get("lead_name"),
			"email": doc.get("email_id"),
			"mobile": doc.get("mobile_no"),
		}
	]


def employee(doc: Any) -> list[Suggestion]:
	user = doc.get("user_id")
	email = (
		doc.get("prefered_email")
		or doc.get("company_email")
		or doc.get("personal_email")
		or (frappe.db.get_value("User", user, "email") if user else None)
	)
	return [
		{
			"party_type": "Employee",
			"party": doc.name,
			"full_name": doc.get("employee_name"),
			"email": email,
			"mobile": doc.get("cell_number"),
		}
	]


def employee_linked(doc: Any) -> list[Suggestion]:
	"""Fallback for DocTypes without their own resolver: the document's Employee, if it has one."""
	found = linked("Employee", doc.get("employee")) if doc.meta.has_field("employee") else None
	return [found] if found else []


def job_offer(doc: Any) -> list[Suggestion]:
	return [
		{
			"party_type": "Job Applicant",
			"party": doc.get("job_applicant"),
			"full_name": doc.get("applicant_name"),
			"email": doc.get("applicant_email"),
		}
	]


def job_applicant(doc: Any) -> list[Suggestion]:
	return [
		{
			"party_type": "Job Applicant",
			"party": doc.name,
			"full_name": doc.get("applicant_name"),
			"email": doc.get("email_id"),
		}
	]
