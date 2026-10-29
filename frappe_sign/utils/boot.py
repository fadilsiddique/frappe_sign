"""Boot data for the SPA shells in www/ (DESIGN 7.1)."""

import frappe
from frappe.utils.jinja_globals import is_rtl

from frappe_sign.utils.languages import SHIPPED, base_language

STAFF_ROLES = frozenset({"Sign Manager", "Sign User", "System Manager"})
MANAGER_ROLES = frozenset({"Sign Manager", "System Manager"})
EMPTY_BRANDING = {"company": None, "logo": None, "brand_color": None}


def base_boot(user: str | None, branding: dict | None = None) -> dict:
	"""Language, direction, branding and the app's translations for `frappe.local.lang`."""
	language = frappe.local.lang or "en"
	return {
		"user": user,
		"lang": language,
		"dir": "rtl" if is_rtl() else "ltr",
		"branding": branding or dict(EMPTY_BRANDING),
		"messages": app_messages(language),
		"languages": list(SHIPPED),
	}


def app_messages(language: str) -> dict[str, str]:
	"""frappe_sign's own translations for the SPAs' __(). English needs none: the source is English."""
	if base_language(language) == "en":
		return {}
	from frappe.translate import get_translations_from_apps

	return get_translations_from_apps(language, ["frappe_sign"])


def profile_branding(company: str | None) -> dict:
	"""Branding from the Sign Profile of `company`, or of the only profile when there is one
	(also when `company`, such as the user's default Company, has no profile)."""
	if not company or not frappe.db.exists("Sign Profile", company):
		profiles = frappe.get_all("Sign Profile", pluck="name", limit=2)
		company = profiles[0] if len(profiles) == 1 else None
	if not company:
		return dict(EMPTY_BRANDING)
	values = frappe.db.get_value("Sign Profile", company, ["logo", "brand_color"], as_dict=True)
	if not values:
		return dict(EMPTY_BRANDING)
	return {"company": company, "logo": values.logo, "brand_color": values.brand_color}


def desk_boot(bootinfo) -> None:
	"""boot_session hook: what public/js/frappe_sign_desk.bundle.js needs to add its buttons (DESIGN 4.1)."""
	if frappe.session.user == "Guest":
		return
	bootinfo.frappe_sign = {
		"enabled_doctypes": frappe.get_all(
			"Sign Enabled DocType",
			filters={"parenttype": "Sign Settings", "parent": "Sign Settings"},
			pluck="reference_doctype",
		),
		"can_send": bool(STAFF_ROLES & set(frappe.get_roles())),
	}
