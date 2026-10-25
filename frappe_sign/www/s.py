"""Guest signing shell at /s/<token>. www/s.html is copied here by the frontend build.

Guests authenticate API calls with the X-Sign-Session header (D10), not cookies, and get no CSRF
token. A logged-in user opening their own signing link (a company-side signer) still has a Frappe
session, so the shell carries that user's CSRF token for the POST calls. Branding comes from the
Sign Profile of the envelope the token belongs to. utils/http.py adds Referrer-Policy: no-referrer.
"""

import frappe

from frappe_sign.utils.boot import base_boot, profile_branding
from frappe_sign.utils.hashing import sha256_hex

no_cache = 1
sitemap = 0


def get_context(context):
	user = frappe.session.user
	logged_in = bool(user) and user != "Guest"
	context.boot = {"frappe_sign": base_boot(user=user if logged_in else None, branding=branding())}
	if logged_in:
		context.boot["csrf_token"] = frappe.sessions.get_csrf_token()


def branding() -> dict:
	"""The envelope company's branding, found from the token in the path (no other data is read)."""
	path = frappe.request.path if getattr(frappe.local, "request", None) else ""
	token = path.strip("/").split("/", 1)[1] if path.strip("/").startswith("s/") else ""
	envelope = token and frappe.db.get_value(
		"Sign Envelope Recipient", {"token_hash": sha256_hex(token), "parenttype": "Sign Envelope"}, "parent"
	)
	company = envelope and frappe.db.get_value("Sign Envelope", envelope, "company")
	return profile_branding(company or None)
