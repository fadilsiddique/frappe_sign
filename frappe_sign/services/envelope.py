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
from frappe.utils.password import get_encryption_key

from frappe_sign.exceptions import FieldValidationError, InvalidTransition, throw
from frappe_sign.pdf.anchors import find_anchors, role_token
from frappe_sign.pdf.pages import extract_pages
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.source import render
from frappe_sign.pdf.types import Anchor, PdfError
from frappe_sign.services import audit, events, notify, settings
from frappe_sign.services.errors import pdf_message
from frappe_sign.services.resolvers import authorised_signatory
from frappe_sign.services.template import load_snapshot
from frappe_sign.utils.dates import after, is_past
from frappe_sign.utils.files import new_private_file, read_file, read_file_url
from frappe_sign.utils.hashing import derive_token, sha256_hex

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
PRINT_FORMAT = "Print Format"
RECIPIENT_FIELDS = ("role_label", "full_name", "email", "mobile", "party_type", "party", "contact")
# Fields added for an anchor that no template field names are required for these types.
REQUIRED_ANCHOR_TYPES = ("Signature", "Initials", "Company Stamp")
# Declared anchor sizes (mm) by marker, or None when the PDF does not come from a Print Format.
Declared = dict[str, tuple[float, float]] | None


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
		"print_format": payload.get("print_format"),
		"letter_head": payload.get("letter_head"),
	}
	if version:
		frappe.has_permission("Sign Template Version", "read", doc=version, throw=True)
		template = from_template(load_snapshot(version), payload.get("recipients") or [])
		# What the sender typed wins over the template's defaults.
		values |= {key: value for key, value in template.items() if not values.get(key)}
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
	attach_source(doc)
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
		# Without a fixed user, the role is the company's authorised signatory (DESIGN 4.3).
		person = role.get("fixed_user") or authorised_signatory(snapshot.get("company"))
		if role.get("signer_source") == "Fixed User" and person and not row.get("email"):
			row["email"] = frappe.db.get_value("User", person, "email")
			row["full_name"] = row.get("full_name") or frappe.utils.get_fullname(person)
		recipients.append(row)
	from_print = snapshot.get("source_type") == PRINT_FORMAT
	return {
		"title": snapshot.get("title"),
		"company": snapshot.get("company"),
		"print_format": snapshot.get("print_format") if from_print else None,
		"letter_head": snapshot.get("letter_head") if from_print else None,
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


@audit.retry_on_conflict
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
	from_print = is_print_source(doc)
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
		if cint(field.page) < 1 and not from_print:
			throw(
				FieldValidationError,
				_("Field {0} is placed by an anchor, which needs a Print Format source.").format(
					field.field_key
				),
			)
	if doc.otp_mode == "WhatsApp":
		throw(FieldValidationError, _("WhatsApp verification is not available yet. Use Email or Off."))
	if from_print and not (doc.reference_doctype and doc.reference_name):
		throw(FieldValidationError, _("Choose the document whose Print Format is sent."))
	if not from_print and not doc.template_version and not doc.source_file:
		throw(FieldValidationError, _("Attach the PDF to send."))
	if not notify.can_send_email(doc.company):
		throw(FieldValidationError, _("Set up an outgoing Email Account before sending."))


@audit.retry_on_conflict
def render_and_send(name: str) -> bool:
	"""Body of jobs.render.run: freeze the PDF, issue tokens, set Sent. False when nothing to do."""
	doc = locked(name)
	if doc.status != DRAFT or doc.send_state != "Queued":
		return False
	try:
		pdf, declared = source_pdf(doc)
		clean = sanitize(pdf, max_bytes=settings.max_upload_bytes(), max_pages=settings.max_pages())
		anchors = find_anchors(clean.data, declared) if declared is not None else []
	except PdfError as error:
		raise SendFailed(pdf_message(error)) from error
	placed = place_anchored_fields(doc, anchors)
	doc = frappe.get_doc("Sign Envelope", name)
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
		payload={
			"original_sha256": clean.sha256,
			"pages": clean.page_count,
			"prefilled": prefilled,
			**placed,
		},
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


def is_print_source(doc: Any) -> bool:
	"""The envelope is rendered from its reference document's Print Format (D5)."""
	if doc.print_format:
		return True
	return (
		bool(doc.template_version) and load_snapshot(doc.template_version).get("source_type") == PRINT_FORMAT
	)


def source_pdf(doc: Any) -> tuple[bytes, Declared]:
	"""The PDF to freeze, and the anchor sizes sign_field() declared when it is a Print Format."""
	if is_print_source(doc):
		rendered = render(doc.reference_doctype, doc.reference_name, doc.print_format, doc.letter_head)
		return rendered.pdf, rendered.declared
	if not doc.template_version:
		return read_file_url(doc.source_file), None
	snapshot = load_snapshot(doc.template_version)
	pdf = read_file_url(snapshot["pdf_file"])
	expected = frappe.db.get_value("Sign Template Version", doc.template_version, "source_sha256")
	if expected and sha256_hex(pdf) != expected:
		raise SendFailed(_("The template PDF changed after it was published. Publish the template again."))
	return pdf, None


def place_anchored_fields(doc: Any, anchors: list[Anchor]) -> dict[str, Any]:
	"""Fields with an anchor_tag take the anchor's page and rect. An anchor that no field names
	becomes a field of the Signer whose role it names (DESIGN 4.2). A required field whose anchor
	is missing fails the send; an optional one is dropped. Called by the render job, while the
	Draft is locked for sending, so rows change directly (DESIGN 2.6)."""
	by_tag = {anchor.tag: anchor for anchor in anchors}
	used = set()
	for field in doc.fields:
		if not field.anchor_tag:
			continue
		anchor = by_tag.get(field.anchor_tag)
		if anchor:
			move_field(field.name, anchor)
			used.add(anchor.tag)
		elif cint(field.page) > 0:
			continue
		elif cint(field.required):
			raise SendFailed(
				_(
					"The Print Format has no sign_field() for {0} ({1}). Add it to the Print Format or make the field optional."
				).format(field.field_key, field.anchor_tag)
			)
		else:
			frappe.db.delete("Sign Envelope Field", {"name": field.name})
	added = add_anchor_fields(doc, [anchor for anchor in anchors if anchor.tag not in used])
	return {
		"anchors": len(anchors),
		"anchor_fields_added": [anchor.tag for anchor in added],
		"unused_anchors": [a.tag for a in anchors if a.tag not in used and a not in added],
	}


def move_field(row: str, anchor: Anchor) -> None:
	frappe.db.set_value(
		"Sign Envelope Field",
		row,
		{"page": anchor.page, "x": anchor.rect.x, "y": anchor.rect.y, "w": anchor.rect.w, "h": anchor.rect.h},
		update_modified=False,
	)


def add_anchor_fields(doc: Any, anchors: list[Anchor]) -> list[Anchor]:
	signers: dict[str, str] = {}
	for row in doc.recipients:
		if row.kind == "Signer":
			try:
				signers[role_token(row.role_label)] = row.role_label
			except ValueError:
				continue
	keys = {field.field_key for field in doc.fields}
	added: list[Anchor] = []
	for anchor in anchors:
		role_label = signers.get(anchor.role)
		if not role_label or anchor.field_type == "Dropdown":
			continue
		key = unique_key(f"{anchor.role}_{anchor.field_type}_{anchor.n}".lower().replace(" ", "_"), keys)
		keys.add(key)
		frappe.get_doc(
			{
				"doctype": "Sign Envelope Field",
				"parent": doc.name,
				"parenttype": "Sign Envelope",
				"parentfield": "fields",
				"idx": len(doc.fields) + len(added) + 1,
				"field_key": key,
				"role_label": role_label,
				"field_type": anchor.field_type,
				"page": anchor.page,
				"x": anchor.rect.x,
				"y": anchor.rect.y,
				"w": anchor.rect.w,
				"h": anchor.rect.h,
				"anchor_tag": anchor.tag,
				"required": int(anchor.field_type in REQUIRED_ANCHOR_TYPES),
				"font_size": 11,
			}
		).insert()
		added.append(anchor)
	return added


def unique_key(key: str, taken: set[str]) -> str:
	candidate, number = key, 1
	while candidate in taken:
		number += 1
		candidate = f"{key}_{number}"
	return candidate


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


def link_token(recipient: str, version: int) -> str:
	return derive_token(get_encryption_key(), recipient, version)


def issue_link(doc: Any, recipient: Any, *, rotate: bool = False) -> str:
	"""The recipient's link token. The current one is re-derived unless `rotate` (resend) or the
	recipient has none yet; a rotated token makes the previous link stop working (D10)."""
	version = cint(recipient.token_version)
	if rotate or version < 1:
		version += 1
	token = link_token(recipient.name, version)
	status = "Sent" if recipient.status == "Pending" else recipient.status
	frappe.db.set_value(
		"Sign Envelope Recipient",
		recipient.name,
		{
			"token_hash": sha256_hex(token),
			"token_version": version,
			"token_expires_on": doc.expires_on,
			"status": status,
		},
		update_modified=False,
	)
	recipient.status = status
	recipient.token_version = version
	return token


def invite(
	doc: Any,
	recipient: Any,
	*,
	event: str = "Delivered",
	payload: dict[str, Any] | None = None,
	rotate: bool = False,
) -> None:
	"""Email the recipient's link and record the event. Reminders resend the same link; `rotate`
	issues a new one."""
	token = issue_link(doc, recipient, rotate=rotate)
	delivered = notify.try_send_invitation(doc, recipient, token, reminder=event == "Reminded")
	audit.append(
		doc.name,
		event,
		recipient_row=recipient.name,
		payload={
			"email": recipient.email,
			"channel": "email",
			"queued": int(delivered),
			"link_version": cint(recipient.token_version),
			**(payload or {}),
		},
	)


def end_sessions(envelope: str, recipient: str | None = None) -> None:
	filters: dict[str, Any] = {"envelope": envelope}
	if recipient:
		filters["recipient_row"] = recipient
	frappe.db.set_value("Sign Session", filters, "expires_on", now_datetime(), update_modified=False)


# Sender actions


@audit.retry_on_conflict
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


@audit.retry_on_conflict
def remind(name: str, recipient: str | None = None) -> int:
	"""Email the link again to recipients whose turn it is. Earlier emails keep working (D10)."""
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
		invite(doc, row, event="Reminded")
	return len(targets)


@audit.retry_on_conflict
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
	invite(doc, row, payload=payload, rotate=True)


def expire(name: str) -> bool:
	"""Expire an open envelope whose expires_on has passed (scheduler, P3.2)."""
	doc = locked(name)
	if doc.status not in OPEN or not is_past(doc.expires_on) or doc.sealing_state != "Not Started":
		return False
	transition(doc, EXPIRED)
	end_sessions(name)
	audit.append(name, "Expired", actor="System")
	events.publish("envelope_expired", name)
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


# Staff helpers


def stage_source(file_name: str, content: bytes) -> dict[str, Any]:
	"""Sanitize an uploaded PDF for a new envelope; create_draft attaches it (source_file)."""
	frappe.has_permission("Sign Envelope", "create", throw=True)
	try:
		clean = sanitize(content, max_bytes=settings.max_upload_bytes(), max_pages=settings.max_pages())
	except PdfError as error:
		throw(FieldValidationError, pdf_message(error))
	file = frappe.get_doc(
		{"doctype": "File", "file_name": file_name or "document.pdf", "content": clean.data, "is_private": 1}
	).insert()
	return {"file_url": file.file_url, "metrics": [metric.to_dict() for metric in clean.metrics]}


def attach_source(envelope: Any) -> None:
	"""Attach a staged source PDF to its new envelope. Only the uploader's own unattached file."""
	if not envelope.source_file:
		return
	file = frappe.db.get_value(
		"File",
		{"file_url": envelope.source_file, "is_private": 1},
		["name", "owner", "attached_to_name"],
		as_dict=True,
		order_by="creation desc",
	)
	if not file or (file.attached_to_name and file.attached_to_name != envelope.name):
		throw(FieldValidationError, _("Upload the PDF again."))
	if file.owner != frappe.session.user and frappe.session.user != "Administrator":
		raise frappe.PermissionError(_("You cannot use a file uploaded by someone else."))
	frappe.db.set_value(
		"File", file.name, {"attached_to_doctype": "Sign Envelope", "attached_to_name": envelope.name}
	)


def download(name: str, kind: str) -> tuple[bytes, str]:
	"""original, signed or certificate (the certificate pages of the signed PDF)."""
	doc = frappe.get_doc("Sign Envelope", name)
	doc.check_permission("read")
	if kind == "original" and doc.original_file:
		data = read_file(doc.original_file)
	elif kind in ("signed", "certificate") and doc.signed_file:
		data = read_file(doc.signed_file)
		if kind == "certificate":
			pages = len(json.loads(doc.page_metrics or "[]"))
			data = extract_pages(data, pages + 1)
	else:
		throw(InvalidTransition, _("There is no {0} PDF for {1} yet.").format(kind, name), status=doc.status)
	audit.append(name, "Downloaded", payload={"kind": kind})
	return data, f"{name}-{kind}.pdf"


def my_signing_link(name: str) -> str:
	"""The /s/<token> link of the logged-in user when it is their turn (DESIGN 5.1). It is the
	same link as in their email (D10)."""
	email = frappe.db.get_value("User", frappe.session.user, "email")
	doc = locked(name)
	require_open(doc)
	row = next(
		(r for r in signing_recipients(doc) if r.email == email and r.status in WAITING and is_turn(doc, r)),
		None,
	)
	if not row:
		throw(InvalidTransition, _("This document is not waiting for your signature."), status=doc.status)
	token = issue_link(doc, row)
	audit.append(name, "Delivered", recipient_row=row.name, payload={"email": email, "channel": "desk"})
	return notify.signing_link(token)


def dashboard() -> dict[str, Any]:
	"""Home cards: needs my signature, waiting for others, completed this month, expiring soon."""
	user = frappe.session.user
	email = frappe.db.get_value("User", user, "email")
	waiting_rows = frappe.get_all(
		"Sign Envelope Recipient",
		filters={"parenttype": "Sign Envelope", "email": email, "status": ["in", WAITING]},
		pluck="parent",
	)
	open_filter = {"status": ["in", OPEN]}
	month_start = frappe.utils.get_first_day(frappe.utils.today())
	soon = after(days=3)
	return {
		"needs_my_signature": frappe.get_list(
			"Sign Envelope",
			filters={**open_filter, "name": ["in", waiting_rows or [""]]},
			fields=["name", "title", "sender", "expires_on"],
			order_by="sent_on desc",
		),
		"waiting_for_others": frappe.db.count("Sign Envelope", {**open_filter, "sender": user}),
		"completed_this_month": frappe.db.count(
			"Sign Envelope", {"status": COMPLETED, "sender": user, "completed_on": [">=", month_start]}
		),
		"expiring_soon": frappe.db.count(
			"Sign Envelope", {**open_filter, "sender": user, "expires_on": ["<=", soon]}
		),
	}
