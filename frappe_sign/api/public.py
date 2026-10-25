"""Public verify API (DESIGN 8.3, 5.6). No document content is returned."""

import base64
import binascii

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit

from frappe_sign.api.errors import with_error_code
from frappe_sign.exceptions import FieldValidationError
from frappe_sign.services import verify as verify_service

MAX_UPLOAD = 25 * 1024 * 1024


@frappe.whitelist(allow_guest=True, methods=["POST"])  # nosemgrep: guest-whitelisted-method
@rate_limit(limit=10, seconds=60)
@with_error_code
def verify(file: str | None = None, envelope: str | None = None) -> dict:
	"""`file` is a multipart upload or a base64 string; `envelope` an envelope ID."""
	content = read_upload(file)
	if not content and not envelope:
		frappe.throw(_("Upload the PDF or enter the envelope ID."), FieldValidationError)
	return verify_service.verify_public(content, (envelope or "").strip() or None)


def read_upload(file: str | None) -> bytes | None:
	upload = frappe.request.files.get("file") if frappe.request and frappe.request.files else None
	if upload:
		data = upload.stream.read(MAX_UPLOAD + 1)
	elif file:
		try:
			data = base64.b64decode(file.split(",", 1)[-1], validate=True)
		except (binascii.Error, ValueError):
			frappe.throw(_("The file could not be read."), FieldValidationError)
	else:
		return None
	if len(data) > MAX_UPLOAD:
		frappe.throw(_("The file is larger than 25 MB."), FieldValidationError)
	return data
