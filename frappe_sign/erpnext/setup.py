"""ERPNext setup: switch company fields to Link Company with Property Setters (DESIGN 2.1).

The `company` fields are Data in the DocType JSON so the app works without ERPNext. With ERPNext,
they become Link Company. Customize Form does not allow a Data to Link change, so the Property
Setters are written here. Both types use the same varchar(140) column, so no data moves.

Values that are not a Company name block the switch: they are reported in the Error Log and the
switch waits until they are fixed (after_migrate tries again). These hooks are imported on every
site; each one returns at once when ERPNext is not installed.
"""

from __future__ import annotations

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

COMPANY_FIELDS = (
	("Sign Profile", "company"),
	("Sign Certificate", "company"),
	("Sign Template", "company"),
	("Sign Envelope", "company"),
)
PROPERTIES = (("fieldtype", "Link", "Select"), ("options", "Company", "Text"))


def erpnext_installed() -> bool:
	return "erpnext" in frappe.get_installed_apps()


def after_install() -> None:
	if erpnext_installed():
		link_company_fields()


def after_app_install(app_name: str) -> None:
	if app_name == "erpnext":
		link_company_fields()


def after_migrate() -> None:
	if erpnext_installed() and not is_linked():
		link_company_fields()


def before_app_uninstall(app_name: str) -> None:
	if app_name == "erpnext":
		unlink_company_fields()


def is_linked() -> bool:
	return all(
		frappe.db.exists(
			"Property Setter",
			{"doc_type": doctype, "field_name": fieldname, "property": "fieldtype", "value": "Link"},
		)
		for doctype, fieldname in COMPANY_FIELDS
	)


def unmatched_values() -> dict[str, list[str]]:
	"""Company values that are not a Company name, by DocType."""
	companies = set(frappe.get_all("Company", pluck="name"))
	found = {}
	for doctype, fieldname in COMPANY_FIELDS:
		values = set(
			frappe.get_all(doctype, filters={fieldname: ["is", "set"]}, pluck=fieldname, distinct=True)
		)
		if values - companies:
			found[doctype] = sorted(values - companies)
	return found


def link_company_fields() -> bool:
	"""Switch every company field to Link Company. False, with an Error Log, when values block it."""
	unmatched = unmatched_values()
	if unmatched:
		lines = [f"{doctype}: {', '.join(values)}" for doctype, values in unmatched.items()]
		frappe.log_error(
			title="Frappe Sign: Link Company",
			message="These company values are not a Company. Rename them to a Company, then run "
			"`bench --site <site> migrate` to switch the company fields to Link Company.\n\n"
			+ "\n".join(lines),
		)
		return False
	for doctype, fieldname in COMPANY_FIELDS:
		for prop, value, property_type in PROPERTIES:
			if not frappe.db.exists(
				"Property Setter", {"doc_type": doctype, "field_name": fieldname, "property": prop}
			):
				make_property_setter(
					doctype, fieldname, prop, value, property_type, validate_fields_for_doctype=False
				)
		frappe.clear_cache(doctype=doctype)
	return True


def unlink_company_fields() -> None:
	for doctype, fieldname in COMPANY_FIELDS:
		frappe.db.delete(
			"Property Setter",
			{"doc_type": doctype, "field_name": fieldname, "property": ["in", [p[0] for p in PROPERTIES]]},
		)
		frappe.clear_cache(doctype=doctype)
