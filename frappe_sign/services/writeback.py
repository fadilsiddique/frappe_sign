"""Write-back to the source document (DESIGN 4.5): signed PDF, sign_status, timeline comments.

Event handlers (hooks.py, frappe_sign_events), each run in its own job as the envelope sender
(D17), so the sender's permissions apply and a failure never touches the signature. They change
the source document with frappe.db.set_value, which works on submitted documents.

- sign_status and sign_envelope are written only when the DocType has them (enabled in Sign
  Settings). A send sets sign_envelope; later events of an older envelope leave the status alone.
- The timeline gets one comment per signature and one for the signed PDF. Handlers can run again
  (a retried job), so each comment and the attachment are added once.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from frappe_sign.utils.dates import format_local
from frappe_sign.utils.files import new_private_file, read_file

SENT, PARTIAL, SIGNED = "Sent", "Partially Signed", "Signed"
DECLINED, VOIDED, EXPIRED = "Declined", "Voided", "Expired"


def on_sent(envelope: str) -> None:
	doc = source_of(envelope)
	if doc:
		set_status(doc, envelope, SENT, claim=True)


def on_partial(envelope: str) -> None:
	"""recipient_signed: a comment per signer, and Partially Signed until the envelope completes."""
	doc = source_of(envelope)
	if not doc:
		return
	envelope_doc = frappe.get_doc("Sign Envelope", envelope)
	for row in envelope_doc.recipients:
		if row.status == "Signed":
			marker = f"{envelope} ({row.role_label}):"
			text = _("signed by {0} on {1}").format(row.full_name, format_local(row.signed_on))
			comment_once(doc, marker, text)
	if envelope_doc.status != "Completed":
		set_status(doc, envelope, PARTIAL)


def on_complete(envelope: str) -> None:
	"""envelope_completed: attach the sealed PDF and set Signed."""
	doc = source_of(envelope)
	if not doc:
		return
	envelope_doc = frappe.get_doc("Sign Envelope", envelope)
	file_name = f"{envelope}-signed.pdf"
	if envelope_doc.signed_file and not frappe.db.exists(
		"File", {"attached_to_doctype": doc.doctype, "attached_to_name": doc.name, "file_name": file_name}
	):
		new_private_file(read_file(envelope_doc.signed_file), file_name, doc.doctype, doc.name).insert()
		comment_once(doc, f"{envelope}:", _("signed by everyone; the sealed PDF is attached."))
	set_status(doc, envelope, SIGNED)


def on_declined(envelope: str) -> None:
	doc = source_of(envelope)
	if doc:
		set_status(doc, envelope, DECLINED)


def on_voided(envelope: str) -> None:
	doc = source_of(envelope)
	if doc:
		set_status(doc, envelope, VOIDED)


def on_expired(envelope: str) -> None:
	doc = source_of(envelope)
	if doc:
		set_status(doc, envelope, EXPIRED)


def source_of(envelope: str) -> Any:
	reference = frappe.db.get_value("Sign Envelope", envelope, ["reference_doctype", "reference_name"])
	if not reference or not all(reference) or not frappe.db.exists(*reference):
		return None
	return frappe.get_doc(*reference)


def set_status(doc: Any, envelope: str, status: str, *, claim: bool = False) -> None:
	"""Write sign_status (and sign_envelope when `claim`) if the DocType has the fields and the
	document follows this envelope."""
	if not has_sign_fields(doc.doctype):
		return
	current = doc.get("sign_envelope")
	if not claim and current and current != envelope:
		return
	frappe.db.set_value(
		doc.doctype, doc.name, {"sign_status": status, "sign_envelope": envelope}, update_modified=False
	)
	doc.notify_update()


def has_sign_fields(doctype: str) -> bool:
	meta = frappe.get_meta(doctype)
	return bool(meta.has_field("sign_status") and meta.has_field("sign_envelope"))


def comment_once(doc: Any, marker: str, text: str) -> None:
	"""A timeline comment "<marker> <text>", unless one with the same marker exists."""
	if frappe.db.exists(
		"Comment",
		{
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"comment_type": "Info",
			"content": ["like", f"{marker}%"],
		},
	):
		return
	doc.add_comment("Info", f"{marker} {text}")
