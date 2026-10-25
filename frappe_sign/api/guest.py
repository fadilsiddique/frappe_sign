"""Guest signing API: token, OTP and X-Sign-Session checks, rate limited (DESIGN 8.2, 5.2).

Every endpoint is POST, open to guests and rate limited. The link token arrives in the body (open,
request_otp, verify_otp); later calls carry the session secret in the X-Sign-Session header, never
a cookie. Failures return a stable `code` (api/errors.py).

Guest access is reviewed (the nosemgrep marks): services/signing.py checks the token or session
before anything else, and tests/security/test_guest_api.py covers limits and scoping.
"""

import base64
import binascii
from collections.abc import Callable
from functools import wraps

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from werkzeug.wrappers import Response

from frappe_sign.api.errors import with_error_code
from frappe_sign.exceptions import FieldValidationError
from frappe_sign.services import signing
from frappe_sign.utils.hashing import sha256_hex

SESSION_HEADER = "X-Sign-Session"
MINUTE, HOUR = 60, 3600
# A base64 image of 2 MB is about 2.7 MB of text; attachments may be 10 MB.
MAX_UPLOAD_CHARS = 14 * 1024 * 1024


def keyed_by_recipient[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
	"""Put sha256(token) in form_dict so @rate_limit can key on the recipient without storing the
	token itself in a Redis key."""

	@wraps(fn)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
		frappe.form_dict["recipient_key"] = sha256_hex(str(frappe.form_dict.get("token") or ""))
		return fn(*args, **kwargs)

	return wrapper


def session_secret() -> str | None:
	return frappe.get_request_header(SESSION_HEADER)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=30, seconds=MINUTE)
@with_error_code
def open(token: str) -> dict:
	return signing.open(token)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@keyed_by_recipient
@rate_limit(key="recipient_key", limit=5, seconds=HOUR, ip_based=False)
@with_error_code
def request_otp(token: str, channel: str = "Email") -> dict:
	return signing.request_otp(token, channel)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=10, seconds=10 * MINUTE)
@with_error_code
def verify_otp(token: str, code: str) -> dict:
	return signing.verify_otp(token, code)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=60, seconds=MINUTE)
@with_error_code
def state() -> dict:
	return signing.state(session_secret())


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=30, seconds=MINUTE)
@with_error_code
def get_pdf() -> Response:
	pdf, file_name = signing.get_pdf(session_secret())
	return Response(
		pdf,
		mimetype="application/pdf",
		headers={
			"Content-Disposition": f'inline; filename="{file_name}"',
			"Cache-Control": "no-store",
			"Referrer-Policy": "no-referrer",
			"X-Content-Type-Options": "nosniff",
		},
	)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=30, seconds=MINUTE)
@with_error_code
def consent(version: int) -> dict:
	signing.consent(session_secret(), version)
	return {"ok": True}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=120, seconds=MINUTE)
@with_error_code
def save_fields(values: dict | str) -> dict:
	return signing.save_fields(session_secret(), frappe.parse_json(values) or {})


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=120, seconds=MINUTE)
@with_error_code
def save_capture(field_key: str, method: str, image: str, file_name: str = "") -> dict:
	return signing.save_capture(session_secret(), field_key, method, decode_upload(image), file_name)


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=10, seconds=MINUTE)
@with_error_code
def finish() -> dict:
	return signing.finish(session_secret())


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=10, seconds=MINUTE)
@with_error_code
def decline(reason: str) -> dict:
	signing.decline(session_secret(), reason)
	return {"status": "Declined"}


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=10, seconds=MINUTE)
@with_error_code
def delegate(full_name: str, email: str) -> dict:
	signing.delegate(session_secret(), full_name, email)
	return {"status": "Delegated"}


def decode_upload(value: str) -> bytes:
	"""A base64 string or data URL from the browser."""
	if not isinstance(value, str) or len(value) > MAX_UPLOAD_CHARS:
		frappe.throw(_("The file is too large."), FieldValidationError)
	if value.startswith("data:"):
		value = value.split(",", 1)[-1]
	try:
		return base64.b64decode(value, validate=True)
	except (binascii.Error, ValueError):
		frappe.throw(_("The file could not be read."), FieldValidationError)
		raise
