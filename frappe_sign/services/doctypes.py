"""Custom fields on the DocTypes enabled in Sign Settings (DESIGN 2.5).

Saving Sign Settings adds `sign_status` and `sign_envelope` to each enabled DocType. Taking a
DocType off the list keeps its fields and their values; remove_custom_fields deletes them on an
admin's explicit request. Both fields allow changes after submit, so write-back works on submitted
documents.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

from frappe_sign.exceptions import FieldValidationError

SIGN_STATUSES = ("Not Sent", "Sent", "Partially Signed", "Signed", "Declined", "Voided", "Expired")
FIELDNAMES = ("sign_status", "sign_envelope")
ADMIN_ROLES = {"System Manager"}


def field_definitions(insert_after: str | None) -> list[dict[str, Any]]:
	common = {"allow_on_submit": 1, "read_only": 1, "no_copy": 1, "print_hide": 1, "report_hide": 0}
	return [
		{
			"fieldname": "sign_status",
			"label": "Signature Status",
			"fieldtype": "Select",
			"options": "\n" + "\n".join(SIGN_STATUSES),
			"in_list_view": 1,
			"in_standard_filter": 1,
			"insert_after": insert_after,
			**common,
		},
		{
			"fieldname": "sign_envelope",
			"label": "Signature Envelope",
			"fieldtype": "Link",
			"options": "Sign Envelope",
			"insert_after": "sign_status",
			**common,
		},
	]


def enabled_doctypes() -> list[str]:
	return frappe.get_all(
		"Sign Enabled DocType",
		filters={"parenttype": "Sign Settings", "parent": "Sign Settings"},
		pluck="reference_doctype",
		order_by="idx asc",
	)


def on_settings_update(doc: Any, method: str | None = None) -> None:
	"""doc_events hook of Sign Settings: give every enabled DocType its fields."""
	add_custom_fields([row.reference_doctype for row in doc.enabled_doctypes])


def add_custom_fields(doctypes: list[str]) -> list[str]:
	"""Create the fields that are missing. Returns the DocTypes that got new fields."""
	changed = []
	for doctype in doctypes:
		meta = frappe.get_meta(doctype)
		missing = [df for df in field_definitions(last_field(meta)) if not meta.has_field(df["fieldname"])]
		for df in missing:
			create_custom_field(doctype, df)
		if missing:
			changed.append(doctype)
	return changed


def last_field(meta: Any) -> str | None:
	fields = [df.fieldname for df in meta.fields if df.fieldname not in FIELDNAMES]
	return fields[-1] if fields else None


def remove_custom_fields(doctype: str) -> int:
	"""Delete the fields from a DocType that is no longer enabled. Their values are lost."""
	if not ADMIN_ROLES & set(frappe.get_roles()):
		raise frappe.PermissionError(_("Only a System Manager can remove the signature fields."))
	if doctype in enabled_doctypes():
		frappe.throw(
			_("Take {0} off the enabled DocTypes in Sign Settings first.").format(doctype),
			FieldValidationError,
		)
	names = frappe.get_all(
		"Custom Field", filters={"dt": doctype, "fieldname": ["in", FIELDNAMES]}, pluck="name"
	)
	for name in names:
		frappe.delete_doc("Custom Field", name)
	return len(names)
