"""Guest signing flow: open, OTP, session, consent, fields, captures, finish, decline, delegate.

The only module allowed to use ignore_permissions, after a token or session check (golden rule 6).

A guest proves who they are with the link token (open, request_otp, verify_otp) and then with the
session secret from the X-Sign-Session header (everything else). Only SHA-256 hashes of tokens,
secrets and OTPs are stored (D10). Responses are scoped to the recipient (DESIGN 5.2).
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, formatdate, now_datetime, today, validate_email_address
from PIL import Image, UnidentifiedImageError

from frappe_sign.exceptions import (
	EnvelopeNotOpen,
	FieldValidationError,
	InvalidTransition,
	LinkExpired,
	NotYourTurn,
	OtpCooldown,
	OtpInvalid,
	RecipientDone,
	SessionInvalid,
	throw,
)
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.types import PdfError
from frappe_sign.services import audit, events, notify, sealing, settings
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services.errors import pdf_message
from frappe_sign.services.pdfs import IMAGE_TYPES, current_pdf_file, filled_pdf
from frappe_sign.services.template import load_snapshot
from frappe_sign.utils.dates import after, is_past, seconds_since
from frappe_sign.utils.files import new_private_file, read_file
from frappe_sign.utils.hashing import new_otp, new_token, same_digest, sha256_hex
from frappe_sign.utils.request import Client, current_client

SESSION_IDLE_MINUTES = 30
SESSION_HOURS = 24
OTP_ATTEMPTS = 5
OTP_COOLDOWN_SECONDS = 60
MAX_TEXT = 500
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_SIDE = 4000
MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
FILE_TYPES = (*IMAGE_TYPES, "Attachment")
CAPTURE_METHODS = ("Draw", "Type", "Upload")
CHECKED, UNCHECKED = "1", "0"


@dataclass
class Access:
	envelope: Any
	recipient: Any
	session: Any = None


# Token and session checks


def by_token(token: str | None) -> Access:
	"""The envelope and recipient of a link token. Unknown and expired tokens look the same."""
	if not token or len(token) > 200:
		throw(LinkExpired, _("This signing link is not valid. Ask the sender for a new one."))
	row = frappe.db.get_value(
		"Sign Envelope Recipient",
		{"token_hash": sha256_hex(token), "parenttype": "Sign Envelope"},
		["name", "parent", "token_expires_on"],
		as_dict=True,
	)
	if not row or is_past(row.token_expires_on):
		throw(LinkExpired, _("This signing link is not valid. Ask the sender for a new one."))
	return load(row.parent, row.name)


def load(envelope_name: str, recipient_row: str, session: Any = None) -> Access:
	envelope = frappe.get_doc("Sign Envelope", envelope_name)
	recipient = next(row for row in envelope.recipients if row.name == recipient_row)
	return Access(envelope, recipient, session)


def by_session(secret: str | None) -> Access:
	"""Check the X-Sign-Session secret: verified, not idle over 30 minutes, under 24 hours old."""
	if not secret or len(secret) > 200:
		throw(SessionInvalid, _("Your signing session has ended. Open the link again."))
	session = frappe.db.get_value(
		"Sign Session",
		{"session_hash": sha256_hex(secret)},
		["name", "envelope", "recipient_row", "verified_on", "last_seen_on", "expires_on"],
		as_dict=True,
	)
	idle = session and seconds_since(session.last_seen_on) > SESSION_IDLE_MINUTES * 60
	if not session or not session.verified_on or is_past(session.expires_on) or idle:
		throw(SessionInvalid, _("Your signing session has ended. Open the link again."))
	frappe.db.set_value("Sign Session", session.name, "last_seen_on", now_datetime(), update_modified=False)
	return load(session.envelope, session.recipient_row, session)


def check_can_act(access: Access) -> None:
	envelope, recipient = access.envelope, access.recipient
	if envelope.status not in envelope_service.OPEN:
		throw(EnvelopeNotOpen, _("This document is {0}.").format(_(envelope.status)), status=envelope.status)
	if recipient.status in envelope_service.DONE:
		throw(RecipientDone, _("You have already responded."), status=recipient.status)
	if not envelope_service.is_turn(envelope, recipient):
		waiting = [
			row.full_name
			for row in envelope_service.signing_recipients(envelope)
			if row.status in envelope_service.WAITING and envelope_service.is_turn(envelope, row)
		]
		throw(
			NotYourTurn,
			_("Waiting for {0} to sign first.").format(", ".join(waiting) or _("another signer")),
			waiting_for=waiting,
		)


def locked(access: Access) -> Access:
	"""Re-read the envelope under its row lock (DESIGN 5.1, step 6)."""
	audit.lock_envelope(access.envelope.name)
	return load(access.envelope.name, access.recipient.name, access.session)


def new_session(access: Access, client: Client, *, verified: bool) -> tuple[str, Any]:
	secret = new_token()
	values: dict[str, Any] = {
		"doctype": "Sign Session",
		"envelope": access.envelope.name,
		"recipient_row": access.recipient.name,
		"last_seen_on": now_datetime(),
		"expires_on": after(minutes=SESSION_HOURS * 60),
		"ip": client.ip,
		"user_agent": client.user_agent,
	}
	if verified:
		values |= {"session_hash": sha256_hex(secret), "verified_on": now_datetime()}
	# Checked first: the link token in by_token (guests have no role that may create sessions).
	session = frappe.get_doc(values).insert(ignore_permissions=True)
	return secret, session


# Open and verify


def open(token: str, client: Client | None = None) -> dict[str, Any]:
	client = client or current_client()
	access = by_token(token)
	check_can_act(access)
	result = summary(access)
	if access.envelope.otp_mode == "Off":
		secret, _session = new_session(access, client, verified=True)
		mark_viewed(access, client)
		result |= {"session": secret, "otp_required": False}
		result["recipient"]["status"] = access.recipient.status
	else:
		result["otp_required"] = True
	return result


def request_otp(token: str, channel: str, client: Client | None = None) -> dict[str, Any]:
	client = client or current_client()
	access = by_token(token)
	check_can_act(access)
	envelope, recipient = access.envelope, access.recipient
	if envelope.otp_mode == "Off" or channel != envelope.otp_mode:
		throw(FieldValidationError, _("Verification by {0} is not used for this document.").format(channel))
	if envelope.otp_mode != "Email":
		throw(FieldValidationError, _("Only email verification is available."))
	last_sent = frappe.db.get_value(
		"Sign Session",
		{"envelope": envelope.name, "recipient_row": recipient.name, "otp_sent_on": ["is", "set"]},
		"otp_sent_on",
		order_by="otp_sent_on desc",
	)
	wait = OTP_COOLDOWN_SECONDS - seconds_since(last_sent)
	if wait > 0:
		throw(
			OtpCooldown,
			_("Wait {0} seconds before asking for a new code.").format(int(wait) + 1),
			retry_after=int(wait) + 1,
		)
	code = new_otp()
	minutes = settings.otp_validity_minutes()
	_secret, session = new_session(access, client, verified=False)
	frappe.db.set_value(
		"Sign Session",
		session.name,
		{
			"otp_hash": sha256_hex(code),
			"otp_sent_on": now_datetime(),
			"otp_expires_on": after(minutes=minutes),
			"otp_attempts": 0,
		},
		update_modified=False,
	)
	notify.send_otp(envelope, recipient, code, minutes)
	audit.append(
		envelope.name,
		"OTP Sent",
		recipient_row=recipient.name,
		actor=recipient.email,
		client=client,
		payload={"channel": "email"},
	)
	return {
		"sent_to": mask_email(recipient.email),
		"expires_in": minutes * 60,
		"retry_after": OTP_COOLDOWN_SECONDS,
	}


def verify_otp(token: str, code: str, client: Client | None = None) -> dict[str, Any]:
	client = client or current_client()
	access = by_token(token)
	check_can_act(access)
	envelope, recipient = access.envelope, access.recipient
	session = frappe.db.get_value(
		"Sign Session",
		{
			"envelope": envelope.name,
			"recipient_row": recipient.name,
			"otp_hash": ["is", "set"],
			"verified_on": ["is", "not set"],
		},
		["name", "otp_hash", "otp_expires_on"],
		order_by="otp_sent_on desc",
		as_dict=True,
	)
	if not session:
		throw(OtpInvalid, _("Ask for a verification code first."), reason="no_code")
	if is_past(session.otp_expires_on):
		throw(OtpInvalid, _("This code has expired. Ask for a new one."), reason="expired")
	attempts = otp_attempts(session.name)
	if attempts >= OTP_ATTEMPTS:
		throw(OtpInvalid, _("Too many wrong codes. Ask for a new one."), reason="too_many")
	if not same_digest(str(code or "").strip(), session.otp_hash):
		attempts = count_otp_attempt(session.name)
		throw(
			OtpInvalid,
			_("The code is not right."),
			reason="wrong",
			attempts_left=max(OTP_ATTEMPTS - attempts, 0),
		)
	secret = new_token()
	frappe.db.set_value(
		"Sign Session",
		session.name,
		{
			"session_hash": sha256_hex(secret),
			"verified_on": now_datetime(),
			"last_seen_on": now_datetime(),
			"otp_hash": None,
			"otp_attempts": attempts,
			"ip": client.ip,
			"user_agent": client.user_agent,
		},
		update_modified=False,
	)
	audit.append(
		envelope.name, "OTP Verified", recipient_row=recipient.name, actor=recipient.email, client=client
	)
	mark_viewed(access, client)
	result = summary(load(envelope.name, recipient.name))
	return result | {"session": secret, "otp_required": False}


def otp_attempts(session: str) -> int:
	"""Wrong codes for a session, kept in Redis: a failed request rolls back the database."""
	return cint(frappe.cache.get_value(otp_key(session)))


def count_otp_attempt(session: str) -> int:
	key = otp_key(session)
	attempts = cint(frappe.cache.get_value(key)) + 1
	frappe.cache.set_value(key, attempts, expires_in_sec=24 * 3600)
	return attempts


def otp_key(session: str) -> str:
	return f"frappe_sign::otp_attempts::{session}"


def mark_viewed(access: Access, client: Client) -> None:
	envelope, recipient = access.envelope, access.recipient
	audit.append(envelope.name, "Viewed", recipient_row=recipient.name, actor=recipient.email, client=client)
	if recipient.status == "Sent":
		frappe.db.set_value(
			"Sign Envelope Recipient",
			recipient.name,
			{"status": "Viewed", "viewed_on": now_datetime()},
			update_modified=False,
		)
		recipient.status = "Viewed"
		events.publish("recipient_viewed", envelope.name)


# Session actions


def state(secret: str) -> dict[str, Any]:
	access = by_session(secret)
	return summary(access)


def consent(secret: str, version: int, client: Client | None = None) -> None:
	access = by_session(secret)
	check_can_act(access)
	_text, current = settings.consent()
	if cint(version) != current:
		throw(FieldValidationError, _("The disclosure changed. Read it again."), consent_version=current)
	audit.append(
		access.envelope.name,
		"Consented",
		recipient_row=access.recipient.name,
		actor=access.recipient.email,
		client=client or current_client(),
		payload={"consent_version": current},
	)


def has_consented(access: Access) -> bool:
	return bool(
		frappe.db.exists(
			"Sign Event",
			{"envelope": access.envelope.name, "recipient_row": access.recipient.name, "event": "Consented"},
		)
	)


def require_consent(access: Access) -> None:
	if not has_consented(access):
		throw(
			FieldValidationError,
			_("Accept the electronic records disclosure first."),
			reason="consent_required",
		)


def get_pdf(secret: str) -> tuple[bytes, str]:
	access = by_session(secret)
	return read_file(current_pdf_file(access.envelope)), f"{access.envelope.name}.pdf"


def own_fields(access: Access) -> dict[str, Any]:
	return {
		row.field_key: row for row in access.envelope.fields if row.recipient_row == access.recipient.name
	}


def save_fields(secret: str, values: dict[str, Any], client: Client | None = None) -> dict[str, Any]:
	access = by_session(secret)
	check_can_act(access)
	require_consent(access)
	fields = own_fields(access)
	cleaned = {}
	for key, value in (values or {}).items():
		field = fields.get(key)
		if not field:
			throw(FieldValidationError, _("Field {0} is not yours to fill.").format(key), field=key)
		if field.read_only or field.field_type in FILE_TYPES or field.field_type == "Date Signed":
			throw(FieldValidationError, _("Field {0} cannot be typed into.").format(key), field=key)
		cleaned[key] = clean_value(field, value)
	for key, value in cleaned.items():
		frappe.db.set_value(
			"Sign Envelope Field",
			fields[key].name,
			{"value": value, "filled_on": now_datetime()},
			update_modified=False,
		)
	if cleaned:
		audit.append(
			access.envelope.name,
			"Field Filled",
			recipient_row=access.recipient.name,
			actor=access.recipient.email,
			client=client or current_client(),
			payload={"fields": sorted(cleaned)},
		)
	return {"fields": recipient_fields(load(access.envelope.name, access.recipient.name))}


def clean_value(field: Any, value: Any) -> str:
	"""Server-side validation by field type, required-ness is checked at finish (DESIGN 5.1)."""
	if field.field_type == "Checkbox":
		return CHECKED if str(value).lower() in ("1", "true", "yes", "on") else UNCHECKED
	text = "" if value is None else str(value).strip()
	if len(text) > MAX_TEXT:
		throw(FieldValidationError, _("{0} is too long.").format(field.field_key), field=field.field_key)
	if not text:
		return ""
	if field.field_type == "Number":
		try:
			float(text.replace(",", ""))
		except ValueError:
			throw(
				FieldValidationError,
				_("{0} must be a number.").format(field.field_key),
				field=field.field_key,
			)
	if field.field_type == "Email" and not validate_email_address(text):
		throw(
			FieldValidationError,
			_("{0} must be an email address.").format(field.field_key),
			field=field.field_key,
		)
	if field.field_type == "Dropdown":
		options = [line.strip() for line in (field.options or "").splitlines() if line.strip()]
		if text not in options:
			throw(
				FieldValidationError,
				_("Choose one of the options for {0}.").format(field.field_key),
				field=field.field_key,
			)
	if field.validation_regex and not re.fullmatch(field.validation_regex, text):
		throw(
			FieldValidationError,
			_("{0} is not in the expected format.").format(field.field_key),
			field=field.field_key,
		)
	return text


def save_capture(
	secret: str,
	field_key: str,
	method: str,
	content: bytes,
	file_name: str = "",
	client: Client | None = None,
) -> dict[str, Any]:
	access = by_session(secret)
	check_can_act(access)
	require_consent(access)
	field = own_fields(access).get(field_key)
	if not field or field.field_type not in FILE_TYPES or field.read_only:
		throw(
			FieldValidationError,
			_("Field {0} does not take a signature or file.").format(field_key),
			field=field_key,
		)
	if method not in CAPTURE_METHODS or (field.field_type == "Attachment" and method != "Upload"):
		throw(FieldValidationError, _("{0} is not a capture method.").format(method), field=field_key)
	envelope = access.envelope
	if field.field_type == "Attachment":
		data, extension = clean_attachment(content or b"", file_name)
	else:
		data, extension = clean_image(content or b""), "png"
	name = f"{envelope.name}-{field_key}-{access.recipient.name[:8]}.{extension}"
	# Checked first: the session secret in by_session and the field's owner above.
	file = new_private_file(data, name, "Sign Envelope", envelope.name).insert(ignore_permissions=True)
	digest = sha256_hex(data)
	values: dict[str, Any] = {"value": file.file_url, "filled_on": now_datetime()}
	if field.field_type in IMAGE_TYPES:
		capture = frappe.get_doc(
			{
				"doctype": "Sign Capture",
				"envelope": envelope.name,
				"recipient_row": access.recipient.name,
				"field_key": field_key,
				"method": method,
				"image": file.file_url,
				"sha256": digest,
			}
		).insert(ignore_permissions=True)  # Checked first: the session secret in by_session.
		values["capture"] = capture.name
	frappe.db.set_value("Sign Envelope Field", field.name, values, update_modified=False)
	audit.append(
		envelope.name,
		"Field Filled",
		recipient_row=access.recipient.name,
		actor=access.recipient.email,
		client=client or current_client(),
		payload={"fields": [field_key], "method": method, "sha256": digest},
	)
	return {"fields": recipient_fields(load(envelope.name, access.recipient.name))}


def clean_image(content: bytes) -> bytes:
	"""A PNG or JPEG under 2 MB, re-encoded as PNG so no metadata or trailing data survives."""
	if len(content) > MAX_IMAGE_BYTES:
		throw(FieldValidationError, _("The image is larger than 2 MB."))
	try:
		with Image.open(io.BytesIO(content)) as image:
			if image.format not in ("PNG", "JPEG"):
				throw(FieldValidationError, _("Use a PNG or JPEG image."))
			if max(image.size) > MAX_IMAGE_SIDE:
				throw(FieldValidationError, _("The image is too large."))
			image.load()
			out = io.BytesIO()
			image.convert("RGBA").save(out, "PNG")
	except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
		throw(FieldValidationError, _("The file is not a readable image."))
	return out.getvalue()


def clean_attachment(content: bytes, file_name: str) -> tuple[bytes, str]:
	if len(content) > MAX_ATTACHMENT_BYTES:
		throw(FieldValidationError, _("The file is larger than 10 MB."))
	if content.startswith(b"%PDF"):
		try:
			return sanitize(
				content, max_bytes=MAX_ATTACHMENT_BYTES, max_pages=settings.max_pages()
			).data, "pdf"
		except PdfError as error:
			throw(FieldValidationError, pdf_message(error))
	return clean_image(content), "png"


def finish(secret: str, client: Client | None = None) -> dict[str, Any]:
	"""Complete this recipient: check, render the intermediate PDF under the row lock (D3)."""
	client = client or current_client()
	access = locked(by_session(secret))
	check_can_act(access)
	require_consent(access)
	envelope, recipient = access.envelope, access.recipient
	if recipient.kind == "Signer":
		fill_automatic_values(access)
		check_required(load(envelope.name, recipient.name))
	envelope = frappe.get_doc("Sign Envelope", envelope.name)
	pdf = filled_pdf(envelope)
	digest = sha256_hex(pdf)
	# Checked first: the session secret in by_session, under the envelope row lock.
	file = new_private_file(
		pdf, f"{envelope.name}-{recipient.name[:8]}.pdf", "Sign Envelope", envelope.name
	).insert(ignore_permissions=True)
	frappe.db.set_value(
		"Sign Envelope Recipient",
		recipient.name,
		{
			"status": "Signed",
			"signed_on": now_datetime(),
			"intermediate_file": file.name,
			"intermediate_sha256": digest,
		},
		update_modified=False,
	)
	if envelope.status == envelope_service.SENT:
		envelope_service.transition(envelope, envelope_service.IN_PROGRESS)
	audit.append(
		envelope.name,
		"Signed",
		recipient_row=recipient.name,
		actor=recipient.email,
		client=client,
		payload={"intermediate_sha256": digest, "kind": recipient.kind},
	)
	envelope.reload()
	completed = all(row.status == "Signed" for row in envelope_service.signing_recipients(envelope))
	if completed:
		sealing.queue_seal(envelope)
	else:
		envelope_service.invite_next(envelope)
	events.publish("recipient_signed", envelope.name)
	return {"status": "Signed", "completed": completed}


def fill_automatic_values(access: Access) -> None:
	"""Date Signed is set now; empty Full Name and Email fields take the recipient's details."""
	recipient = access.recipient
	for field in own_fields(access).values():
		value = None
		if field.field_type == "Date Signed":
			value = formatdate(today())
		elif field.field_type == "Full Name" and not field.value:
			value = recipient.full_name
		elif field.field_type == "Email" and not field.value:
			value = recipient.email
		if value is not None:
			frappe.db.set_value(
				"Sign Envelope Field",
				field.name,
				{"value": value, "filled_on": now_datetime()},
				update_modified=False,
			)


def check_required(access: Access) -> None:
	missing = [
		field.field_key
		for field in own_fields(access).values()
		if cint(field.required) and not field.read_only and not is_filled(field)
	]
	if missing:
		throw(FieldValidationError, _("Fill in every required field first."), missing=missing)


def is_filled(field: Any) -> bool:
	if field.field_type in IMAGE_TYPES:
		return bool(field.capture)
	if field.field_type == "Checkbox":
		return field.value == CHECKED
	return bool((field.value or "").strip())


def decline(secret: str, reason: str, client: Client | None = None) -> None:
	reason = (reason or "").strip()
	if not reason:
		throw(FieldValidationError, _("Tell the sender why you decline."))
	access = locked(by_session(secret))
	check_can_act(access)
	envelope, recipient = access.envelope, access.recipient
	frappe.db.set_value(
		"Sign Envelope Recipient",
		recipient.name,
		{"status": "Declined", "decline_reason": reason[:1000]},
		update_modified=False,
	)
	envelope_service.transition(envelope, envelope_service.DECLINED)
	envelope_service.end_sessions(envelope.name)
	audit.append(
		envelope.name,
		"Declined",
		recipient_row=recipient.name,
		actor=recipient.email,
		client=client or current_client(),
		payload={"reason": reason[:1000]},
	)
	events.publish("envelope_declined", envelope.name)


def can_delegate(access: Access) -> bool:
	if not access.envelope.template_version or access.recipient.kind == "CC":
		return False
	roles = load_snapshot(access.envelope.template_version).get("roles") or []
	return any(
		role["role_label"] == access.recipient.role_label and cint(role.get("can_delegate")) for role in roles
	)


def delegate(secret: str, full_name: str, email: str, client: Client | None = None) -> None:
	full_name, email = (full_name or "").strip(), (email or "").strip().lower()
	access = locked(by_session(secret))
	check_can_act(access)
	if not can_delegate(access):
		throw(InvalidTransition, _("This document cannot be passed on to someone else."))
	if not full_name or len(full_name) > 140 or not validate_email_address(email):
		throw(FieldValidationError, _("Enter the name and email address of the person who will sign."))
	envelope, old = access.envelope, access.recipient
	if email == (old.email or "").lower():
		throw(FieldValidationError, _("Enter someone else's email address."))
	# A service may add rows to a sent envelope only by inserting them directly (DESIGN 2.6).
	new = frappe.get_doc(
		{
			"doctype": "Sign Envelope Recipient",
			"parent": envelope.name,
			"parenttype": "Sign Envelope",
			"parentfield": "recipients",
			"idx": len(envelope.recipients) + 1,
			"role_label": old.role_label,
			"routing_order": old.routing_order,
			"kind": old.kind,
			"full_name": full_name,
			"email": email,
			"status": "Pending",
		}
	).insert(ignore_permissions=True)  # Checked first: the session secret in by_session.
	frappe.db.set_value(
		"Sign Envelope Recipient",
		old.name,
		{"status": "Delegated", "delegated_to": new.name},
		update_modified=False,
	)
	for field in own_fields(access).values():
		frappe.db.set_value(
			"Sign Envelope Field", field.name, "recipient_row", new.name, update_modified=False
		)
	envelope_service.end_sessions(envelope.name, old.name)
	audit.append(
		envelope.name,
		"Delegated",
		recipient_row=old.name,
		actor=old.email,
		client=client or current_client(),
		payload={"to_row": new.name, "to_name": full_name, "to_email": email},
	)
	envelope = frappe.get_doc("Sign Envelope", envelope.name)
	envelope_service.invite(envelope, next(row for row in envelope.recipients if row.name == new.name))


# Recipient-scoped views


def summary(access: Access) -> dict[str, Any]:
	envelope, recipient = access.envelope, access.recipient
	consent_text, consent_version = settings.consent()
	return {
		"envelope": {
			"title": envelope.title,
			"message": envelope.message,
			"sender_name": frappe.utils.get_fullname(envelope.sender) if envelope.sender else "",
			"company": envelope.company,
			"status": envelope.status,
			"expires_on": str(envelope.expires_on) if envelope.expires_on else None,
		},
		"recipient": {
			"full_name": recipient.full_name,
			"email": recipient.email,
			"role_label": recipient.role_label,
			"kind": recipient.kind,
			"status": recipient.status,
			"can_delegate": can_delegate(access),
		},
		"otp_mode": envelope.otp_mode,
		"consent": {"text": consent_text, "version": consent_version, "given": has_consented(access)},
		"pages": frappe.parse_json(envelope.page_metrics or "[]"),
		"fields": recipient_fields(access),
	}


def recipient_fields(access: Access) -> list[dict[str, Any]]:
	return [
		{
			"key": field.field_key,
			"type": field.field_type,
			"page": cint(field.page),
			"rect": {"x": field.x, "y": field.y, "w": field.w, "h": field.h},
			"required": bool(cint(field.required)),
			"read_only": bool(cint(field.read_only)),
			"value": None if field.field_type in FILE_TYPES else field.value,
			"filled": is_filled(field),
			"options": [line for line in (field.options or "").splitlines() if line.strip()],
			"font_size": field.font_size,
		}
		for field in sorted(own_fields(access).values(), key=lambda f: (cint(f.page), f.y or 0, f.x or 0))
	]


def mask_email(email: str | None) -> str:
	if not email or "@" not in email:
		return ""
	local, domain = email.split("@", 1)
	return f"{local[:1]}{'*' * max(len(local) - 1, 2)}@{domain}"
