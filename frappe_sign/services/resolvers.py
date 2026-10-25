"""Suggested recipients for a document (DESIGN 4.3).

Resolvers are registered per DocType under the `frappe_sign_resolvers` hook; `"*"` is the fallback
for DocTypes without their own. A resolver takes the document and returns suggestions:
`{party_type, party, contact, full_name, email, mobile}`. Resolvers read fields with `doc.get()`,
so a missing field or record means "unresolved", never an exception. The send dialog always lets
the user correct the result.

resolve_recipients() maps a template's roles to recipients by their signer source:

- Fixed User: the role's user, or the Sign Profile's authorised signatory when the role names none.
- Doc Field: the value at `source_field`: an email address, or a link to a User, Contact or any
  DocType with a resolver (Customer, Employee...).
- Party Contact: the document's own resolver.
- Employee: the document's `employee` field, resolved as an Employee.
- Ask at Send: left for the sender.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe
from frappe.utils import get_fullname, validate_email_address

from frappe_sign.services import notify
from frappe_sign.services.template import load_snapshot

SUGGESTION_FIELDS = ("party_type", "party", "contact", "full_name", "email", "mobile")
FALLBACK = "*"

Suggestion = dict[str, Any]
Resolver = Callable[[Any], list[Suggestion]]


def resolver_for(doctype: str) -> Resolver | None:
	hooks = frappe.get_hooks("frappe_sign_resolvers", {})
	paths = hooks.get(doctype) or hooks.get(FALLBACK) or []
	return frappe.get_attr(paths[-1]) if paths else None


def suggest(doctype: str, name: str) -> list[Suggestion]:
	"""Suggestions for a document the user may read. Unknown records give none."""
	if not (doctype and name) or not frappe.db.exists(doctype, name):
		return []
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("read")
	return suggestions_of(doc)


def suggestions_of(doc: Any) -> list[Suggestion]:
	resolver = resolver_for(doc.doctype)
	if not resolver:
		return []
	return [clean(row) for row in resolver(doc) or [] if row]


def linked(doctype: str | None, name: str | None) -> Suggestion | None:
	"""The first suggestion for a linked record, read without its own permission check: the user
	reads it through the document that links to it."""
	if not (doctype and name) or not frappe.db.exists(doctype, name):
		return None
	rows = suggestions_of(frappe.get_doc(doctype, name))
	return rows[0] if rows else None


def clean(row: Suggestion) -> Suggestion:
	values = {field: row.get(field) or None for field in SUGGESTION_FIELDS}
	email = (values["email"] or "").strip()
	values["email"] = email if email and validate_email_address(email) else None
	return values


# Core resolvers (Frappe DocTypes)


def contact(doc: Any) -> list[Suggestion]:
	return [contact_suggestion(doc)]


def contact_suggestion(doc: Any) -> Suggestion:
	email = doc.get("email_id") or next(
		(row.email_id for row in doc.get("email_ids") or [] if row.get("is_primary")), None
	)
	full_name = doc.get("full_name") or " ".join(
		part for part in (doc.get("first_name"), doc.get("last_name")) if part
	)
	return {
		"contact": doc.name,
		"full_name": full_name or None,
		"email": email,
		"mobile": doc.get("mobile_no") or doc.get("phone"),
	}


def contact_details(name: str | None) -> Suggestion | None:
	if not name or not frappe.db.exists("Contact", name):
		return None
	return contact_suggestion(frappe.get_doc("Contact", name))


def user(doc: Any) -> list[Suggestion]:
	return [user_suggestion(doc.name)]


def user_suggestion(name: str) -> Suggestion:
	return {
		"full_name": get_fullname(name),
		"email": frappe.db.get_value("User", name, "email"),
		"mobile": frappe.db.get_value("User", name, "mobile_no"),
	}


# Template roles


def resolve_recipients(template: str, doctype: str | None, name: str | None) -> list[dict[str, Any]]:
	"""One row per role of the template's published version, with what could be resolved."""
	frappe.has_permission("Sign Template", "read", doc=template, throw=True)
	version = frappe.db.get_value("Sign Template", template, "published_version")
	if not version:
		frappe.throw(frappe._("Template {0} has no published version.").format(template))
	snapshot = load_snapshot(version)
	doc = None
	if doctype and name and frappe.db.exists(doctype, name):
		doc = frappe.get_doc(doctype, name)
		doc.check_permission("read")
	company = (doc.get("company") if doc else None) or snapshot.get("company")
	rows = []
	for role in sorted(snapshot.get("roles") or [], key=lambda r: int(r.get("routing_order") or 0)):
		found = role_suggestion(role, doc, company) or {}
		rows.append(
			{
				"role_label": role["role_label"],
				"kind": role.get("kind") or "Signer",
				"routing_order": role.get("routing_order") or 1,
				"signer_source": role.get("signer_source"),
				**clean(found),
				"resolved": bool(found.get("email")),
			}
		)
	return rows


def role_suggestion(role: dict[str, Any], doc: Any, company: str | None) -> Suggestion | None:
	source = role.get("signer_source")
	if source == "Fixed User":
		person = role.get("fixed_user") or authorised_signatory(company)
		return user_suggestion(person) if person else None
	if doc is None:
		return None
	if source == "Party Contact":
		rows = suggestions_of(doc)
		return rows[0] if rows else None
	if source == "Employee":
		return linked("Employee", doc.get("employee"))
	if source == "Doc Field":
		return field_suggestion(doc, role.get("source_field"))
	return None


def field_suggestion(doc: Any, fieldname: str | None) -> Suggestion | None:
	if not fieldname:
		return None
	value = doc.get(fieldname)
	if not value or not isinstance(value, str):
		return None
	if validate_email_address(value):
		return {"email": value}
	df = doc.meta.get_field(fieldname)
	if not df:
		return None
	target = (
		df.options
		if df.fieldtype == "Link"
		else doc.get(df.options)
		if df.fieldtype == "Dynamic Link"
		else None
	)
	if target == "User":
		return user_suggestion(value) if frappe.db.exists("User", value) else None
	if target == "Contact":
		return contact_details(value)
	return linked(target, value) if target else None


def authorised_signatory(company: str | None) -> str | None:
	profile = company if company and frappe.db.exists("Sign Profile", company) else notify.single_profile()
	return frappe.db.get_value("Sign Profile", profile, "authorised_signatory") if profile else None


def primary_party(rows: list[dict[str, Any]]) -> tuple[str | None, str | None]:
	"""Party type and party of the first Signer row that has one, for the envelope's dashboards."""
	for row in rows:
		if row.get("kind") == "Signer" and row.get("party_type") and row.get("party"):
			return row["party_type"], row["party"]
	return None, None
