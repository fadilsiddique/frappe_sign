"""Staff API for logged-in users, under Frappe permissions (DESIGN 8.1). Phase 1 subset.

Each function parses input, calls one service and shapes the output. Permission checks live in the
services (doc.check_permission) and in the Sign Envelope permission hooks.
"""

import base64

import frappe
from frappe.rate_limiter import rate_limit
from werkzeug.wrappers import Response

from frappe_sign.api.errors import with_error_code
from frappe_sign.services import audit, doctypes, documents, preview, resolvers, sealing
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import template as template_service
from frappe_sign.utils.dates import format_utc


@frappe.whitelist()
@with_error_code
def get_dashboard() -> dict:
	return envelope_service.dashboard()


@frappe.whitelist(methods=["POST"])
@with_error_code
def create_envelope(payload: dict | str) -> dict:
	doc = envelope_service.create_draft(frappe.parse_json(payload))
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
@with_error_code
def send_envelope(envelope: str) -> dict:
	envelope_service.send(envelope)
	return {"name": envelope, "send_state": "Queued"}


@frappe.whitelist(methods=["POST"])
@with_error_code
def retry_seal(envelope: str) -> dict:
	sealing.retry_seal(envelope)
	return {"name": envelope, "sealing_state": "Queued"}


@frappe.whitelist(methods=["POST"])
@rate_limit(limit=20, seconds=3600)
@with_error_code
def remind(envelope: str, recipient: str | None = None) -> dict:
	return {"reminded": envelope_service.remind(envelope, recipient)}


@frappe.whitelist(methods=["POST"])
@with_error_code
def resend(envelope: str, recipient: str, email: str | None = None) -> dict:
	envelope_service.resend(envelope, recipient, email)
	return {"name": envelope}


@frappe.whitelist(methods=["POST"])
@with_error_code
def void_envelope(envelope: str, reason: str) -> dict:
	envelope_service.void(envelope, reason)
	return {"name": envelope, "status": "Voided"}


@frappe.whitelist()
@with_error_code
def download(envelope: str, kind: str = "signed") -> Response:
	data, file_name = envelope_service.download(envelope, kind)
	return Response(
		data,
		mimetype="application/pdf",
		headers={"Content-Disposition": f'attachment; filename="{file_name}"', "Cache-Control": "no-store"},
	)


@frappe.whitelist()
@with_error_code
def get_envelope(envelope: str) -> dict:
	"""Detail page: the envelope, its recipients and the audit timeline (Sign Events are read here
	after the envelope permission check, since Sign Users have no role on Sign Event)."""
	doc = frappe.get_doc("Sign Envelope", envelope)
	doc.check_permission("read")
	events = frappe.get_all(
		"Sign Event",
		filters={"envelope": envelope},
		fields=["seq", "event", "at", "actor", "ip", "recipient_row"],
		order_by="seq asc",
	)
	return {
		"envelope": {
			field: doc.get(field)
			for field in (
				"name",
				"title",
				"status",
				"send_state",
				"send_error",
				"sealing_state",
				"sender",
				"company",
				"message",
				"sent_on",
				"expires_on",
				"completed_on",
				"signing_order",
				"otp_mode",
				"original_sha256",
				"signed_sha256",
				"audit_head",
				"void_reason",
				"page_metrics",
			)
		},
		"recipients": [
			{
				field: row.get(field)
				for field in (
					"name",
					"role_label",
					"kind",
					"routing_order",
					"full_name",
					"email",
					"status",
					"signed_on",
					"viewed_on",
					"decline_reason",
				)
			}
			for row in doc.recipients
		],
		"events": [{**event, "at": format_utc(event.at)} for event in events],
		"chain_ok": audit.verify_chain(envelope).ok,
		"can_write": bool(doc.has_permission("write")),
	}


@frappe.whitelist(methods=["POST"])
@with_error_code
def my_signing_link(envelope: str) -> dict:
	return {"url": envelope_service.my_signing_link(envelope)}


@frappe.whitelist(methods=["POST"])
@with_error_code
def publish_template(template: str) -> dict:
	version = template_service.publish(template)
	return {"name": version.name, "version_no": version.version_no}


@frappe.whitelist(methods=["POST"])
@with_error_code
def save_template(template: str | None = None, data: dict | str | None = None) -> dict:
	"""Create or update a template from the designer (roles and fields included)."""
	values = frappe.parse_json(data) or {}
	doc = (
		template_service.update_template(template, values)
		if template
		else template_service.create_template(values)
	)
	return {"name": doc.name, "modified": str(doc.modified)}


@frappe.whitelist(methods=["POST"])
@with_error_code
def upload_pdf(
	template: str | None = None, file_name: str = "document.pdf", content: str | None = None
) -> dict:
	"""Upload a PDF as multipart `file` or base64 `content`. With `template`, it becomes the
	template's PDF; without, it is staged for a new envelope (send wizard)."""
	file_name, data = uploaded_pdf(file_name, content)
	if template:
		return {"metrics": template_service.upload_pdf(template, file_name, data)}
	return envelope_service.stage_source(file_name, data)


def uploaded_pdf(file_name: str, content: str | None) -> tuple[str, bytes]:
	upload = frappe.request.files.get("file") if frappe.request and frappe.request.files else None
	if upload:
		return upload.filename or file_name, upload.stream.read()
	if content and content.startswith("data:"):
		content = content.split(",", 1)[-1]
	return file_name, base64.b64decode(content or "")


@frappe.whitelist(methods=["POST"])
@with_error_code
def remove_sign_fields(doctype: str) -> dict:
	"""System Manager: delete sign_status and sign_envelope from a DocType no longer enabled."""
	return {"removed": doctypes.remove_custom_fields(doctype)}


@frappe.whitelist()
@with_error_code
def resolve_recipients(template: str, doctype: str | None = None, name: str | None = None) -> list:
	"""The template's roles with the recipients found on the document (DESIGN 4.3)."""
	return resolvers.resolve_recipients(template, doctype, name)


@frappe.whitelist()
@with_error_code
def document_templates(doctype: str) -> list:
	"""Published templates for the Desk send dialog, the Sign Settings default first."""
	return documents.templates_for(doctype)


@frappe.whitelist(methods=["POST"])
@with_error_code
def send_from_document(
	doctype: str,
	name: str,
	template: str,
	recipients: list | str,
	message: str | None = None,
	print_format: str | None = None,
	letter_head: str | None = None,
) -> dict:
	"""Desk send dialog: create the envelope from the template and send it."""
	envelope = documents.send_from_document(
		doctype,
		name,
		template,
		frappe.parse_json(recipients) or [],
		message=message,
		print_format=print_format,
		letter_head=letter_head,
	)
	return {"name": envelope, "send_state": "Queued"}


@frappe.whitelist(methods=["POST"])
@with_error_code
def bulk_send(doctype: str, names: list | str, template: str) -> dict:
	"""List view: one envelope per selected document, queued (jobs.bulk.run)."""
	return {"queued": documents.queue_bulk_send(doctype, frappe.parse_json(names) or [], template)}


@frappe.whitelist(methods=["POST"])
@with_error_code
def preview_source(
	doctype: str, name: str, print_format: str | None = None, letter_head: str | None = None
) -> dict:
	"""Send wizard: render the Print Format and return the anchors found (cached 5 minutes)."""
	return preview.preview_source(doctype, name, print_format, letter_head)


@frappe.whitelist()
@with_error_code
def preview_pdf(key: str) -> Response:
	return Response(
		preview.preview_pdf(key),
		mimetype="application/pdf",
		headers={"Content-Disposition": "inline", "Cache-Control": "no-store"},
	)


@frappe.whitelist()
@with_error_code
def preview_prefill(template: str, doctype: str, name: str) -> list:
	return preview.preview_prefill(template, doctype, name)
