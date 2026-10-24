"""Staff app shell at /sign. www/sign.html is copied here by the frontend build."""

from urllib.parse import quote

import frappe
from frappe import _

from frappe_sign.utils.boot import STAFF_ROLES, base_boot, profile_branding

no_cache = 1
sitemap = 0


def get_context(context):
	if frappe.session.user == "Guest":
		path = frappe.request.path if getattr(frappe.local, "request", None) else "/sign"
		frappe.local.flags.redirect_location = f"/login?redirect-to={quote(path)}"
		# 302, not the default 301: browsers cache a 301 and would keep sending a logged-in user to login.
		raise frappe.Redirect(302)

	if not STAFF_ROLES.intersection(frappe.get_roles()):
		raise frappe.PermissionError(_("You need the Sign User or Sign Manager role to open Frappe Sign."))

	company = frappe.defaults.get_user_default("company")
	context.boot = {
		"csrf_token": frappe.sessions.get_csrf_token(),
		"frappe_sign": base_boot(frappe.session.user, profile_branding(company)),
	}
