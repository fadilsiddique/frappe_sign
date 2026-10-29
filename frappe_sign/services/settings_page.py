"""What the staff app's Settings page reads and changes (UX_PLAN "Settings", U.9).

A Sign Manager and a System Manager can see everything here. Only a System Manager changes it:
the page edits site-wide setup (seals, the DocTypes that get custom fields, timestamp servers).
Reads use frappe.db and frappe.get_all after that role check, because a Sign Manager cannot open
a Sign Certificate or an Email Account in Desk. Nothing here returns a secret.
"""

from __future__ import annotations

import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import certificates, doctypes, setup

VIEW_ROLES = ["Sign Manager", "System Manager"]
ADMIN_ROLE = "System Manager"
SETTINGS = "Sign Settings"
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")

PROFILE_FIELDS = ("logo", "brand_color", "legal_footer", "sender_email_account", "authorised_signatory")
SECTION_FIELDS = {
	"signing": ("default_expiry_days", "default_reminder_days", "otp_validity_minutes", "consent_text"),
	"advanced": ("tsa_urls", "max_upload_mb", "max_pages"),
}
DOCTYPE_SEARCH_LIMIT = 20


def overview() -> dict[str, Any]:
	frappe.only_for(VIEW_ROLES)
	settings = frappe.get_doc(SETTINGS)
	return {
		"can_edit": ADMIN_ROLE in frappe.get_roles(),
		"has_erpnext": "erpnext" in frappe.get_installed_apps(),
		"profiles": [profile_card(name) for name in profile_names()],
		"companies": companies_without_profile(),
		"email_accounts": outgoing_accounts(),
		"signatories": signatory_choices(),
		"documents": [document_row(row) for row in settings.enabled_doctypes],
		"signing": {field: settings.get(field) for field in SECTION_FIELDS["signing"]},
		"advanced": {field: settings.get(field) for field in SECTION_FIELDS["advanced"]},
	}


def profile_names() -> list[str]:
	return frappe.get_all("Sign Profile", pluck="name", order_by="creation asc")


def profile_card(name: str) -> dict[str, Any]:
	values = frappe.db.get_value("Sign Profile", name, [*PROFILE_FIELDS, "sealing_certificate"], as_dict=True)
	return {
		"company": name,
		**{field: values.get(field) for field in PROFILE_FIELDS},
		"seal": certificates.seal_details(values.sealing_certificate),
		"sender": sender_status(name, values.sender_email_account),
	}


def sender_status(profile: str, account: str | None) -> dict[str, str | None]:
	"""connected: the profile's own account sends; default: the site's outgoing account does;
	missing: nothing can send."""
	email_id = setup.outgoing_email(profile)
	if not email_id:
		return {"status": "missing", "email_id": None}
	return {"status": "connected" if account else "default", "email_id": email_id}


def companies_without_profile() -> list[str]:
	if "erpnext" not in frappe.get_installed_apps():
		return []
	have = set(profile_names())
	return [name for name in frappe.get_all("Company", pluck="name", order_by="name asc") if name not in have]


def outgoing_accounts() -> list[dict[str, str]]:
	return frappe.get_all(
		"Email Account", filters={"enable_outgoing": 1}, fields=["name", "email_id"], order_by="name asc"
	)


def signatory_choices() -> list[dict[str, str]]:
	return frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Administrator", "Guest"]]},
		fields=["name", "full_name"],
		order_by="full_name asc",
		limit=200,
	)


def document_row(row: Any) -> dict[str, Any]:
	return {
		"doctype": row.reference_doctype,
		"default_template": row.default_template,
		"templates": frappe.get_all(
			"Sign Template",
			filters={
				"reference_doctype": row.reference_doctype,
				"is_active": 1,
				"published_version": ["is", "set"],
			},
			fields=["name", "title"],
			order_by="title asc",
		),
		"sends": frappe.db.count("Sign Envelope", {"reference_doctype": row.reference_doctype}),
	}


def require_admin() -> None:
	frappe.only_for(ADMIN_ROLE)


def save_profile(company: str, values: dict[str, Any]) -> dict[str, Any]:
	"""Create the company's Sign Profile if it has none, then set its logo, color, sender and
	signatory. Fields that are not in `values` stay as they are."""
	require_admin()
	company = (company or "").strip()
	if not company:
		throw(FieldValidationError, _("Choose the company."))
	unknown = set(values) - set(PROFILE_FIELDS)
	if unknown:
		throw(FieldValidationError, _("Unknown profile fields: {0}.").format(", ".join(sorted(unknown))))
	color = values.get("brand_color")
	if color and not HEX_COLOR.match(color):
		throw(FieldValidationError, _("Enter the color as #RRGGBB, for example #0f766e."))
	if frappe.db.exists("Sign Profile", company):
		profile = frappe.get_doc("Sign Profile", company)
	else:
		profile = frappe.get_doc({"doctype": "Sign Profile", "company": company})
	profile.update({field: (value or None) for field, value in values.items()})
	profile.save()
	return profile_card(profile.name)


def save_settings(section: str, values: dict[str, Any]) -> dict[str, Any]:
	"""Change the fields of one Settings tab ("signing" or "advanced") on Sign Settings."""
	require_admin()
	allowed = SECTION_FIELDS.get(section)
	if allowed is None:
		throw(FieldValidationError, _("Unknown settings section {0}.").format(section))
	unknown = set(values) - set(allowed)
	if unknown:
		throw(FieldValidationError, _("Unknown fields: {0}.").format(", ".join(sorted(unknown))))
	settings = frappe.get_doc(SETTINGS)
	for field, value in values.items():
		settings.set(field, cint(value) if field.endswith(("_days", "_minutes", "_mb", "_pages")) else value)
	settings.save()
	return {field: settings.get(field) for field in allowed}


def enable_doctype(doctype: str) -> dict[str, Any]:
	"""Let people send this DocType for signature. Saving adds its two custom fields."""
	require_admin()
	settings = frappe.get_doc(SETTINGS)
	if doctype in doctypes.enabled_doctypes():
		throw(FieldValidationError, _("{0} is already on the list.").format(_(doctype)))
	settings.append("enabled_doctypes", {"reference_doctype": doctype})
	settings.save()
	return document_row(settings.enabled_doctypes[-1])


def disable_doctype(doctype: str) -> None:
	"""Stop sending this DocType. Its custom fields and their values stay."""
	require_admin()
	settings = frappe.get_doc(SETTINGS)
	rows = [row for row in settings.enabled_doctypes if row.reference_doctype != doctype]
	if len(rows) == len(settings.enabled_doctypes):
		throw(FieldValidationError, _("{0} is not on the list.").format(_(doctype)))
	settings.set("enabled_doctypes", rows)
	settings.save()


def set_default_template(doctype: str, template: str | None) -> dict[str, Any]:
	"""The template the send wizard picks first for a DocType. Empty clears it."""
	require_admin()
	settings = frappe.get_doc(SETTINGS)
	row = next((row for row in settings.enabled_doctypes if row.reference_doctype == doctype), None)
	if row is None:
		throw(FieldValidationError, _("{0} is not on the list.").format(_(doctype)))
	if template:
		check_default_template(doctype, template)
	row.default_template = template or None
	settings.save()
	return document_row(row)


def check_default_template(doctype: str, template: str) -> None:
	values = frappe.db.get_value(
		"Sign Template", template, ["reference_doctype", "is_active", "published_version"], as_dict=True
	)
	if not values or values.reference_doctype != doctype or not values.is_active:
		throw(FieldValidationError, _("Choose a template made for {0}.").format(_(doctype)))
	if not values.published_version:
		throw(FieldValidationError, _("Publish the template before making it the default."))


def doctype_choices(query: str = "") -> list[str]:
	"""DocTypes that can be turned on: documents, not child tables, singles or our own."""
	require_admin()
	filters: dict[str, Any] = {
		"istable": 0,
		"issingle": 0,
		"module": ["!=", "Frappe Sign"],
		"name": ["like", f"%{query.strip()}%"],
	}
	rows = frappe.get_all(
		"DocType", filters=filters, pluck="name", order_by="name asc", limit=DOCTYPE_SEARCH_LIMIT
	)
	enabled = set(doctypes.enabled_doctypes())
	return [name for name in rows if name not in enabled]
