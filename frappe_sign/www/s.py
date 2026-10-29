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
	envelope = envelope_of_token()
	values = (
		frappe.db.get_value("Sign Envelope", envelope, ["company", "language"], as_dict=True)
		if envelope
		else None
	)
	use_language((values or {}).get("language"))
	branding = profile_branding((values or {}).get("company") or None)
	context.boot = {"frappe_sign": base_boot(user=user if logged_in else None, branding=branding)}
	if logged_in:
		context.boot["csrf_token"] = frappe.sessions.get_csrf_token()


def envelope_of_token() -> str | None:
	"""The envelope the token in the path belongs to (no other data is read)."""
	path = frappe.request.path if getattr(frappe.local, "request", None) else ""
	token = path.strip("/").split("/", 1)[1] if path.strip("/").startswith("s/") else ""
	if not token:
		return None
	return frappe.db.get_value(
		"Sign Envelope Recipient", {"token_hash": sha256_hex(token), "parenttype": "Sign Envelope"}, "parent"
	)


def use_language(envelope_language: str | None) -> None:
	"""The sender chose the language of this document. A signer's own choice (?_lang=ar, or the
	language cookie the switch sets) wins over it; otherwise the browser's language would."""
	if not envelope_language or frappe.form_dict.get("_lang") or request_cookie("preferred_language"):
		return
	frappe.local.lang = envelope_language


def request_cookie(name: str) -> str | None:
	request = getattr(frappe.local, "request", None)
	return request.cookies.get(name) if request else None
