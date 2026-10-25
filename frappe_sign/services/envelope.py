"""Envelope lifecycle: create draft, send, void, remind, resend, expire (DESIGN 3).

Past Draft an envelope changes only here and in signing.py / sealing.py, through db_set under the
envelope row lock (audit.lock_envelope). Every status change goes through transition(), which
refuses moves the state machine does not allow.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, now_datetime, validate_email_address

from frappe_sign.exceptions import FieldValidationError, InvalidTransition, throw
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.types import PdfError
from frappe_sign.services import audit, events, notify, settings
from frappe_sign.services.errors import pdf_message
from frappe_sign.services.template import load_snapshot
from frappe_sign.utils.dates import after, is_past
from frappe_sign.utils.files import new_private_file, read_file, read_file_url
from frappe_sign.utils.hashing import new_token, sha256_hex

DRAFT, SENT, IN_PROGRESS = "Draft", "Sent", "In Progress"
COMPLETED, DECLINED, VOIDED, EXPIRED = "Completed", "Declined", "Voided", "Expired"
OPEN = (SENT, IN_PROGRESS)
TRANSITIONS: dict[str, set[str]] = {
	DRAFT: {SENT},
	SENT: {IN_PROGRESS, DECLINED, VOIDED, EXPIRED},
	IN_PROGRESS: {COMPLETED, DECLINED, VOIDED, EXPIRED},
}
SIGNING_KINDS = ("Signer", "Approver")
# Recipients whose turn has come and who have not finished.
WAITING = ("Sent", "Viewed")
DONE = ("Signed", "Declined", "Delegated")
UPLOADED_PDF = "Uploaded PDF"
RECIPIENT_FIELDS = ("role_label", "full_name", "email", "mobile", "party_type", "party", "contact")


class SendFailed(Exception):
	"""The render job cannot freeze the PDF; the envelope stays Draft with send_state Failed."""


def transition(envelope: Any, to: str, **values: Any) -> None:
	"""Move an envelope to `to` with db_set. The caller holds the row lock."""
	if to not in TRANSITIONS.get(envelope.status, set()):
		throw(
			InvalidTransition,
			_("Sign Envelope {0} is {1} and cannot become {2}.").format(
				envelope.name, _(envelope.status), _(to)
			),
			status=envelope.status,
		)
	envelope.db_set({"status": to, **values})


def locked(name: str) -> Any:
	"""The envelope, read after taking its row lock."""
	audit.lock_envelope(name)
	return frappe.get_doc("Sign Envelope", name)


def require_open(envelope: Any) -> None:
	if envelope.status not in OPEN:
		throw(
			InvalidTransition,
			_("Sign Envelope {0} is {1}.").format(envelope.name, _(envelope.status)),
			status=envelope.status,
		)


# Draft


def create_draft(payload: dict[str, Any]) -> Any:
	"""A Draft from a published template version, or from an uploaded PDF (`source_file`)."""
	version = payload.get("template_version")
	values: dict[str, Any] = {
		"doctype": "Sign Envelope",
		"title": payload.get("title"),
		"company": payload.get("company"),
		"message": payload.get("message"),
		"reference_doctype": payload.get("reference_doctype"),
		"reference_name": payload.get("reference_name"),
		"party_type": payload.get("party_type"),
		"party": payload.get("party"),
	}
	if version:
		frappe.has_permission("Sign Template Version", "read", doc=version, throw=True)
		values |= from_template(load_snapshot(version), payload.get("recipients") or [])
		values["template_version"] = version
	else:
		values |= {
			"source_file": payload.get("source_file"),
			"signing_order": payload.get("signing_order") or "Sequential",
			"otp_mode": payload.get("otp_mode") or "Off",
			"recipients": [recipient_row(row) for row in payload.get("recipients") or []],
			"fields": payload.get("fields") or [],
		}
	values["title"] = values["title"] or _("Document for signature")
	doc = frappe.get_doc(values).insert()
	audit.append(doc.name, "Created", payload={"template_version": version} if version else None)
	return doc


def from_template(snapshot: dict[str, Any], given: list[dict[str, Any]]) -> dict[str, Any]:
	by_role = {row.get("role_label"): row for row in given}
	recipients = []
	for role in sorted(snapshot.get("roles") or [], key=lambda r: cint(r.get("routing_order"))):
		row = recipient_row(by_role.get(role["role_label"]) or {})
		row |= {
			"role_label": role["role_label"],
			"kind": role["kind"],
			"routing_order": role.get("routing_order") or 1,
		}
		if role.get("signer_source") == "Fixed User" and role.get("fixed_user") and not row.get("email"):
			row["email"] = frappe.db.get_value("User", role["fixed_user"], "email")
			row["full_name"] = row.get("full_name") or frappe.utils.get_fullname(role["fixed_user"])
		recipients.append(row)
	return {
		"title": snapshot.get("title"),
		"company": snapshot.get("company"),
		"signing_order": snapshot.get("signing_order") or "Sequential",
		"otp_mode": snapshot.get("otp_mode") or "Off",
		"recipients": recipients,
		"fields": [dict(field) for field in snapshot.get("fields") or []],
	}


def recipient_row(row: dict[str, Any]) -> dict[str, Any]:
	values = {field: row.get(field) for field in RECIPIENT_FIELDS if row.get(field)}
	values["kind"] = row.get("kind") or "Signer"
	values["routing_order"] = cint(row.get("routing_order")) or 1
	return values


# Send


def send(name: str) -> None:
	"""Check the Draft, set send_state Queued and enqueue the render job (DESIGN 3)."""
	doc = frappe.get_doc("Sign Envelope", name)
	doc.check_permission("write")
	doc = locked(name)
	if doc.status != DRAFT:
		throw(InvalidTransition, _("Only a Draft can be sent."), status=doc.status)
	if doc.send_state == "Queued":
		throw(InvalidTransition, _("This envelope is already being sent."), status=doc.status)
	check_sendable(doc)
	doc.db_set({"send_state": "Queued", "send_error": None})
	frappe.enqueue(
		"frappe_sign.jobs.render.run",
		queue="default",
		enqueue_after_commit=True,
		job_id=f"frappe_sign::render::{name}",
		deduplicate=True,
		envelope=name,
	)


def check_sendable(doc: Any) -> None:
	signing = [row for row in doc.recipients if row.kind in SIGNING_KINDS]
	if not signing:
		throw(FieldValidationError, _("Add at least one Signer or Approver."))
	labels = [row.role_label for row in doc.recipients]
	if len(labels) != len(set(labels)) or not all(labels):
		throw(FieldValidationError, _("Each recipient needs its own role label."))
	for row in doc.recipients:
		if not row.full_name or not row.email or not validate_email_address(row.email):
			throw(
				FieldValidationError,
				_("Recipient {0} needs a name and a valid email address.").format(row.role_label),
			)
	signers = {row.role_label for row in doc.recipients if row.kind == "Signer"}
	for field in doc.fields:
		if field.role_label not in signers:
			throw(
				FieldValidationError,
				_("Field {0} belongs to {1}, which is not a Signer here.").format(
					field.field_key, field.role_label
				),
			)
		if cint(field.page) < 1:
			throw(
				FieldValidationError,
				_("Field {0} is placed by an anchor, which needs a Print Format source.").format(
					field.field_key
				),
			)
	if doc.otp_mode == "WhatsApp":
		throw(FieldValidationError, _("WhatsApp verification is not available yet. Use Email or Off."))
	if not doc.template_version and not doc.source_file:
		throw(FieldValidationError, _("Attach the PDF to send."))
	if not notify.can_send_email(doc.company):
		throw(FieldValidationError, _("Set up an outgoing Email Account before sending."))


def render_and_send(name: str) -> bool:
	"""Body of jobs.render.run: freeze the PDF, issue tokens, set Sent. False when nothing to do."""
	doc = locked(name)
	if doc.status != DRAFT or doc.send_state != "Queued":
		return False
	try:
		clean = sanitize(
			source_pdf(doc), max_bytes=settings.max_upload_bytes(), max_pages=settings.max_pages()
		)
	except PdfError as error:
		raise SendFailed(pdf_message(error)) from error
	for field in doc.fields:
		if cint(field.page) > clean.page_count:
			raise SendFailed(
				_("Field {0} is on page {1}, but the PDF has {2} pages.").format(
					field.field_key, field.page, clean.page_count
				)
			)
	file = new_private_file(clean.data, f"{name}-original.pdf", "Sign Envelope", name).insert()
	prefilled = apply_prefill(doc)
	assign_fields(doc)
	expires_on = after(days=expiry_days(doc))
	doc.db_set(
		{
			"original_file": file.name,
			"original_sha256": clean.sha256,
			"page_metrics": json.dumps([metric.to_dict() for metric in clean.metrics]),
			"send_state": "Not Started",
			"send_error": None,
			"expires_on": expires_on,
		}
	)
	transition(doc, SENT, sent_on=now_datetime())
	audit.append(
		name,
		"Sent",
		payload={"original_sha256": clean.sha256, "pages": clean.page_count, "prefilled": prefilled},
	)
	invite_next(doc)
	events.publish("envelope_sent", name)
	return True


def mark_send_failed(name: str, reason: str) -> None:
	doc = frappe.get_doc("Sign Envelope", name)
	if doc.status != DRAFT:
		return
	doc.db_set({"send_state": "Failed", "send_error": reason[:1000]})
	notify.send_failed(name, reason)


def source_pdf(doc: Any) -> bytes:
	if not doc.template_version:
		return read_file_url(doc.source_file)
	snapshot = load_snapshot(doc.template_version)
	if snapshot.get("source_type") != UPLOADED_PDF:
		raise SendFailed(
			_("Print Format sources are not available yet. Use a template with an uploaded PDF.")
		)
	pdf = read_file_url(snapshot["pdf_file"])
	expected = frappe.db.get_value("Sign Template Version", doc.template_version, "source_sha256")
	if expected and sha256_hex(pdf) != expected:
		raise SendFailed(_("The template PDF changed after it was published. Publish the template again."))
	return pdf


def expiry_days(doc: Any) -> int:
	if doc.template_version:
		days = cint(load_snapshot(doc.template_version).get("expiry_days"))
		if days > 0:
			return days
	return settings.expiry_days()


def apply_prefill(doc: Any) -> dict[str, str]:
	"""Values from the source document for fields with prefill_path (DESIGN 4.4)."""
	if not (doc.reference_doctype and doc.reference_name):
		return {}
	source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
	source.check_permission("read")
	prefilled = {}
	for field in doc.fields:
		if not field.prefill_path:
			continue
		if "{{" in field.prefill_path:
			# Written by a Sign Manager on the template; frappe renders it in its sandboxed Jinja.
			value = frappe.render_template(field.prefill_path, {"doc": source})  # nosemgrep: frappe-ssti
		else:
			value = source.get(field.prefill_path)
		value = "" if value is None else str(value)
		frappe.db.set_value("Sign Envelope Field", field.name, "value", value, update_modified=False)
		prefilled[field.field_key] = value
	return prefilled


def assign_fields(doc: Any) -> None:
	rows = {row.role_label: row.name for row in doc.recipients}
	for field in doc.fields:
		frappe.db.set_value(
			"Sign Envelope Field", field.name, "recipient_row", rows[field.role_label], update_modified=False
		)


# Invitations


def signing_recipients(doc: Any) -> list[Any]:
	return [row for row in doc.recipients if row.kind in SIGNING_KINDS and row.status != "Delegated"]


def current_order(doc: Any) -> int | None:
	"""Routing order whose turn it is in sequential mode; None when every signer finished."""
	pending = [cint(row.routing_order) for row in signing_recipients(doc) if row.status not in DONE]
	return min(pending) if pending else None


def is_turn(doc: Any, recipient: Any) -> bool:
	if doc.signing_order == "Parallel":
		return True
	return cint(recipient.routing_order) == current_order(doc)


def invite_next(doc: Any) -> None:
	"""Invite the recipients whose turn has come and who have no link yet."""
	doc.reload()
	for row in signing_recipients(doc):
		if row.status == "Pending" and is_turn(doc, row):
			invite(doc, row)


def invite(
	doc: Any, recipient: Any, *, event: str = "Delivered", payload: dict[str, Any] | None = None
) -> None:
	"""Issue a new token (the old one stops working), email the link and record the event."""
	token = new_token()
	status = "Sent" if recipient.status == "Pending" else recipient.status
	frappe.db.set_value(
		"Sign Envelope Recipient",
		recipient.name,
		{"token_hash": sha256_hex(token), "token_expires_on": doc.expires_on, "status": status},
		update_modified=False,
	)
	recipient.status = status
	delivered = notify.try_send_invitation(doc, recipient, token, reminder=event == "Reminded")
	audit.append(
		doc.name,
		event,
		recipient_row=recipient.name,
		payload={"email": recipient.email, "channel": "email", "queued": int(delivered), **(payload or {})},
	)


def end_sessions(envelope: str, recipient: str | None = None) -> None:
	filters: dict[str, Any] = {"envelope": envelope}
	if recipient:
		filters["recipient_row"] = recipient
	frappe.db.set_value("Sign Session", filters, "expires_on", now_datetime(), update_modified=False)


# Sender actions


def void(name: str, reason: str) -> None:
	frappe.get_doc("Sign Envelope", name).check_permission("write")
	if not (reason or "").strip():
		throw(FieldValidationError, _("Give a reason for voiding."))
	doc = locked(name)
	require_open(doc)
	if doc.sealing_state in ("Queued", "Sealing", "Sealed"):
		throw(InvalidTransition, _("Everyone has signed; the envelope is being sealed."), status=doc.status)
	transition(doc, VOIDED, void_reason=reason.strip()[:1000])
	end_sessions(name)
	audit.append(name, "Voided", payload={"reason": reason.strip()[:1000]})
	events.publish("envelope_voided", name)


def remind(name: str, recipient: str | None = None) -> int:
	"""Email a fresh link to recipients whose turn it is. Returns how many were reminded."""
	frappe.get_doc("Sign Envelope", name).check_permission("write")
	doc = locked(name)
	require_open(doc)
	targets = [
		row
		for row in signing_recipients(doc)
		if row.status in WAITING and (not recipient or row.name == recipient)
	]
	if recipient and not targets:
		throw(InvalidTransition, _("This recipient is not waiting to sign."), status=doc.status)
	for row in targets:
		end_sessions(name, row.name)
		invite(doc, row, event="Reminded")
	return len(targets)


def resend(name: str, recipient: str, email: str | None = None) -> None:
	"""A new link for one waiting recipient, optionally to a corrected email address."""
	frappe.get_doc("Sign Envelope", name).check_permission("write")
	doc = locked(name)
	require_open(doc)
	row = next((r for r in doc.recipients if r.name == recipient), None)
	if not row or row.status not in WAITING:
		throw(InvalidTransition, _("This recipient is not waiting to sign."), status=doc.status)
	payload: dict[str, Any] = {"resend": 1}
	if email and email != row.email:
		if not validate_email_address(email):
			throw(FieldValidationError, _("{0} is not a valid email address.").format(email))
		payload["previous_email"] = row.email
		frappe.db.set_value("Sign Envelope Recipient", row.name, "email", email, update_modified=False)
		row.email = email
	end_sessions(name, row.name)
	invite(doc, row, payload=payload)


def expire(name: str) -> bool:
	"""Expire an open envelope whose expires_on has passed (scheduler, P3.2)."""
	doc = locked(name)
	if doc.status not in OPEN or not is_past(doc.expires_on) or doc.sealing_state != "Not Started":
		return False
	transition(doc, EXPIRED)
	end_sessions(name)
	audit.append(name, "Expired", actor="System")
	return True


def expire_due() -> list[str]:
	names = frappe.get_all(
		"Sign Envelope",
		filters={"status": ["in", OPEN], "expires_on": ["<", now_datetime()], "sealing_state": "Not Started"},
		pluck="name",
	)
	return [name for name in names if expire(name)]


def original_pdf(doc: Any) -> bytes:
	return read_file(doc.original_file)


def record_send_crash(name: str) -> None:
	"""The render job failed unexpectedly: log the traceback and tell the sender."""
	frappe.log_error(title="Frappe Sign: send", reference_doctype="Sign Envelope", reference_name=name)
	mark_send_failed(name, _("Sending failed unexpectedly. The details are in the Error Log."))
