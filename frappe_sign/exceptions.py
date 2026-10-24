"""Domain errors with HTTP status codes and stable codes (DESIGN 8.4).

The frontend switches UI states on `code`, never on the message text, so a code must not change
once released.
"""

import frappe


class FrappeSignError(frappe.ValidationError):
	http_status_code = 417
	code = "frappe_sign_error"


class EnvelopeNotOpen(FrappeSignError):
	http_status_code = 409
	code = "envelope_not_open"


class NotYourTurn(FrappeSignError):
	http_status_code = 409
	code = "not_your_turn"


class OtpRequired(FrappeSignError):
	http_status_code = 401
	code = "otp_required"


class OtpInvalid(FrappeSignError):
	http_status_code = 401
	code = "otp_invalid"


class LinkExpired(FrappeSignError):
	http_status_code = 410
	code = "link_expired"


class InvalidTransition(FrappeSignError):
	http_status_code = 409
	code = "invalid_transition"


class FieldValidationError(FrappeSignError):
	http_status_code = 422
	code = "field_validation_error"


class CertificateError(FrappeSignError):
	http_status_code = 500
	code = "certificate_error"


class ImmutableRecord(FrappeSignError):
	"""An insert-only record, or an envelope past Draft, was changed outside a service (DESIGN 2.6)."""

	http_status_code = 409
	code = "immutable_record"
