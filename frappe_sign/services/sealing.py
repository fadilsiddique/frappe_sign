"""Sealing (DESIGN 5.4): exactly one PAdES-B-LT seal per envelope.

1. signing.finish holds the envelope row lock, sees every Signer and Approver done and calls
   queue_seal: sealing_state Not Started -> Queued, and one deduplicated jobs.seal.run.
2. The job calls begin (Queued -> Sealing under the lock) and commits, then run: overlay, certificate,
   seal, store, Sealed, Completed. A second job finds sealing_state Sealing or Sealed and stops.
3. On failure the job calls fail: Failed, and the scheduler retries after 1, 5 and 30 minutes
   (retry_due). After the last retry the sender is alerted; a Sign Manager can retry_seal.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, now_datetime
from frappe.utils.password import get_decrypted_password

from frappe_sign.crypto.signer import Pkcs12Signer, Signer
from frappe_sign.exceptions import CertificateError, InvalidTransition, throw
from frappe_sign.pdf.certificate import (
	CertificateData,
	CertificateEvent,
	CertificateSigner,
	append_certificate,
	render_certificate,
)
from frappe_sign.pdf.seal import seal_pdf
from frappe_sign.pdf.text import default_fonts
from frappe_sign.services import audit, certificates, events, notify, settings
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services.pdfs import IMAGE_TYPES, filled_pdf
from frappe_sign.utils.dates import after, format_local, format_utc
from frappe_sign.utils.files import new_private_file, read_file, read_file_url
from frappe_sign.utils.hashing import sha256_hex
from frappe_sign.utils.users import run_as

JOB = "frappe_sign.jobs.seal.run"
BACKOFF_MINUTES = (1, 5, 30)
MANAGER_ROLES = {"Sign Manager", "System Manager"}


def job_id(envelope: str) -> str:
	return f"frappe_sign::seal::{envelope}"


def enqueue_seal(envelope: str) -> None:
	frappe.enqueue(
		JOB,
		queue="long",
		timeout=900,
		job_id=job_id(envelope),
		deduplicate=True,
		enqueue_after_commit=True,
		envelope=envelope,
	)


def queue_seal(envelope: Any) -> bool:
	"""Not Started -> Queued and enqueue the seal job. The caller holds the envelope row lock."""
	if envelope.sealing_state != "Not Started":
		return False
	envelope.db_set("sealing_state", "Queued")
	enqueue_seal(envelope.name)
	return True


@audit.retry_on_conflict
def retry_seal(name: str) -> None:
	"""A Sign Manager starts a new seal after sealing_state Failed."""
	if not MANAGER_ROLES & set(frappe.get_roles()):
		raise frappe.PermissionError(_("Only a Sign Manager can retry sealing."))
	doc = envelope_service.locked(name)
	if doc.sealing_state != "Failed":
		throw(InvalidTransition, _("Only a failed seal can be retried."), sealing_state=doc.sealing_state)
	doc.db_set({"sealing_state": "Queued", "seal_retry_on": None})
	enqueue_seal(name)


@audit.retry_on_conflict
def begin(name: str) -> bool:
	"""Queued -> Sealing under the row lock. False when another job already took it."""
	doc = envelope_service.locked(name)
	if doc.sealing_state != "Queued" or doc.status != envelope_service.IN_PROGRESS:
		return False
	doc.db_set("sealing_state", "Sealing")
	return True


def run(name: str) -> None:
	"""Build, seal and store the final PDF. Runs as the sender, whose permissions apply."""
	doc = frappe.get_doc("Sign Envelope", name)
	with run_as(doc.sender or "Administrator"):
		head = audit.head(name)
		sealed = build_sealed_pdf(doc, head)
		complete(name, sealed, head)


def build_sealed_pdf(doc: Any, head: str | None) -> bytes:
	certificate = render_certificate(certificate_data(doc, head or ""), default_fonts())
	combined = append_certificate(filled_pdf(doc), certificate)
	return seal_pdf(
		combined,
		signer=sealing_signer(doc.company),
		tsa_urls=settings.tsa_urls(),
		reason=_("Signed with Frappe Sign"),
		location=doc.company or "",
		contact=frappe.db.get_value("User", doc.sender, "email") or "",
		**seal_options(),
	)


def seal_options() -> dict[str, Any]:
	"""Extra seal_pdf arguments. Tests return an offline timestamper and validation context."""
	return {}


def complete(name: str, sealed: bytes, head: str | None) -> None:
	doc = envelope_service.locked(name)
	if doc.sealing_state != "Sealing":
		return
	file = new_private_file(sealed, f"{name}-signed.pdf", "Sign Envelope", name).insert()
	digest = sha256_hex(sealed)
	doc.db_set(
		{
			"signed_file": file.name,
			"signed_sha256": digest,
			"audit_head": head,
			"sealing_state": "Sealed",
			"seal_retry_on": None,
		}
	)
	envelope_service.transition(doc, envelope_service.COMPLETED, completed_on=now_datetime())
	for row in doc.recipients:
		if row.kind == "CC":
			frappe.db.set_value("Sign Envelope Recipient", row.name, "status", "Sent", update_modified=False)
	audit.append(name, "Sealed", actor="System", payload={"signed_sha256": digest, "audit_head": head})
	audit.append(name, "Completed", actor="System")
	events.publish("envelope_completed", name)


@audit.retry_on_conflict
def fail(name: str, reason: str) -> None:
	"""Record a failed attempt after the job rolled back, and schedule the next retry."""
	doc = envelope_service.locked(name)
	if doc.sealing_state not in ("Queued", "Sealing"):
		return
	attempts = cint(doc.seal_attempts) + 1
	retry_on = after(minutes=BACKOFF_MINUTES[attempts - 1]) if attempts <= len(BACKOFF_MINUTES) else None
	doc.db_set({"sealing_state": "Failed", "seal_attempts": attempts, "seal_retry_on": retry_on})
	frappe.log_error(
		title="Frappe Sign: seal",
		message=f"Attempt {attempts} failed: {reason}\n\n{frappe.get_traceback()}",
		reference_doctype="Sign Envelope",
		reference_name=name,
	)
	if retry_on is None:
		notify.send_failed(name, _("Sealing failed after {0} attempts: {1}").format(attempts, reason))


def retry_due() -> list[str]:
	"""Scheduler: queue failed seals whose retry time has come."""
	due = frappe.get_all(
		"Sign Envelope",
		filters={"sealing_state": "Failed", "seal_retry_on": ["<=", now_datetime()]},
		pluck="name",
	)
	queued = []
	for name in due:
		doc = envelope_service.locked(name)
		if doc.sealing_state == "Failed" and doc.seal_retry_on and doc.seal_retry_on <= now_datetime():
			doc.db_set({"sealing_state": "Queued", "seal_retry_on": None})
			enqueue_seal(name)
			queued.append(name)
	return queued


def sealing_signer(company: str | None) -> Signer:
	profile = company or notify.single_profile()
	certificate = profile and frappe.db.get_value("Sign Profile", profile, "sealing_certificate")
	if not certificate:
		throw(
			CertificateError,
			_("Set a sealing certificate on the Sign Profile of {0}.").format(profile or _("this site")),
		)
	if frappe.db.get_value("Sign Certificate", certificate, "storage") == "Remote":
		return certificates.remote_signer(certificate)
	p12_file = frappe.db.get_value("Sign Certificate", certificate, "p12_file")
	password = get_decrypted_password("Sign Certificate", certificate, "p12_password", raise_exception=False)
	if not p12_file or not password:
		throw(
			CertificateError, _("Sign Certificate {0} has no PKCS#12 file or password.").format(certificate)
		)
	return Pkcs12Signer(read_file_url(p12_file), password.encode())


def certificate_data(doc: Any, head: str) -> CertificateData:
	branding = (
		frappe.db.get_value(
			"Sign Profile",
			doc.company or notify.single_profile() or "",
			["logo", "brand_color", "legal_footer"],
			as_dict=True,
		)
		or frappe._dict()
	)
	events_rows = frappe.get_all(
		"Sign Event",
		filters={"envelope": doc.name},
		fields=["at", "event", "actor", "ip", "recipient_row"],
		order_by="seq asc",
	)
	signed_ip = {row.recipient_row: row.ip for row in events_rows if row.event == "Signed"}
	return CertificateData(
		envelope=doc.name,
		title=doc.title,
		company=doc.company,
		brand_color=branding.brand_color,
		logo=read_logo(branding.logo),
		legal_footer=branding.legal_footer,
		sender=f"{frappe.utils.get_fullname(doc.sender)} ({frappe.db.get_value('User', doc.sender, 'email')})",
		sent_at=format_local(doc.sent_on),
		completed_at=format_local(now_datetime()),
		original_sha256=doc.original_sha256,
		audit_head=head,
		verify_url=frappe.utils.get_url(f"/sign-verify?envelope={doc.name}"),
		signers=[
			CertificateSigner(
				name=row.full_name,
				email=row.email,
				role=row.role_label,
				kind=_(row.kind),
				signed_at=format_local(row.signed_on),
				ip=signed_ip.get(row.name),
				intermediate_sha256=row.intermediate_sha256,
				signature=signature_of(doc, row.name),
			)
			for row in envelope_service.signing_recipients(doc)
		],
		events=[
			CertificateEvent(at=format_utc(row.at), event=_(row.event), actor=row.actor, ip=row.ip)
			for row in events_rows
		],
		labels=certificate_labels(),
	)


def signature_of(doc: Any, recipient_row: str) -> bytes | None:
	field = next(
		(
			row
			for row in doc.fields
			if row.recipient_row == recipient_row and row.field_type in IMAGE_TYPES[:2] and row.capture
		),
		None,
	)
	if not field:
		return None
	image = frappe.db.get_value("Sign Capture", field.capture, "image")
	file_name = frappe.db.get_value("File", {"file_url": image, "attached_to_name": doc.name}, "name")
	return read_file(file_name) if file_name else None


def read_logo(file_url: str | None) -> bytes | None:
	if not file_url:
		return None
	try:
		return read_file_url(file_url)
	except (frappe.DoesNotExistError, OSError):
		return None


def certificate_labels() -> dict[str, str]:
	return {
		"heading": _("Certificate of Completion"),
		"envelope": _("Envelope"),
		"document": _("Document"),
		"company": _("Company"),
		"sender": _("Sent by"),
		"sent_at": _("Sent"),
		"completed_at": _("Completed"),
		"original_sha256": _("Original PDF SHA-256"),
		"audit_head": _("Audit chain head"),
		"signers": _("Signers"),
		"name": _("Name"),
		"role": _("Role"),
		"signed_at": _("Signed"),
		"ip": _("IP address"),
		"intermediate_sha256": _("PDF SHA-256 at signing"),
		"events": _("Audit trail"),
		"at": _("Time"),
		"event": _("Event"),
		"actor": _("By"),
		"verify": _("Scan or open the link to verify this document:"),
		"page": _("Page {0}"),
		"sealed_note": _("The completed PDF, including this certificate, is sealed with a PAdES signature."),
	}
