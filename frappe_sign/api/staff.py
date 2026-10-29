"""Staff API for logged-in users, under Frappe permissions (DESIGN 8.1). Phase 1 subset.

Each function parses input, calls one service and shapes the output. Permission checks live in the
services (doc.check_permission) and in the Sign Envelope permission hooks.
"""

import base64

import frappe
from frappe.rate_limiter import rate_limit
from werkzeug.wrappers import Response

from frappe_sign.api.errors import with_error_code
from frappe_sign.services import (
	audit,
	cards,
	certificates,
	doctypes,
	documents,
	home,
	pickers,
	preview,
	requests,
	resolvers,
	sealing,
	settings_page,
	setup,
	template_catalog,
)
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import template as template_service
from frappe_sign.utils.dates import format_utc, utc_now


@frappe.whitelist()
@with_error_code
def get_dashboard() -> dict:
	return home.dashboard()


@frappe.whitelist()
@with_error_code
def get_setup_status() -> dict:
	return setup.setup_status()


@frappe.whitelist()
@with_error_code
def list_requests(
	status: str = "open",
	search: str | None = None,
	reference_doctype: str | None = None,
	sender: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	start: int = 0,
	limit: int = 50,
) -> dict:
	return requests.list_requests(status, search, reference_doctype, sender, date_from, date_to, start, limit)


@frappe.whitelist()
@with_error_code
def request_counts(
	search: str | None = None,
	reference_doctype: str | None = None,
	sender: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
) -> dict:
	return requests.request_counts(search, reference_doctype, sender, date_from, date_to)


@frappe.whitelist()
@with_error_code
def request_filter_options() -> dict:
	return requests.filter_options()


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
def waiting_on(envelope: str) -> list:
	return requests.waiting_on(envelope)


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
				"reference_doctype",
				"reference_name",
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
		"events": [
			{
				**event,
				"at": format_utc(event.at),
				"ago_seconds": max(0, int((utc_now() - event.at).total_seconds())),
			}
			for event in events
		],
		"chain_ok": audit.verify_chain(envelope).ok,
		"can_write": bool(doc.has_permission("write")),
	}


@frappe.whitelist(methods=["POST"])
@with_error_code
def my_signing_link(envelope: str) -> dict:
	return {"url": envelope_service.my_signing_link(envelope)}


@frappe.whitelist(methods=["POST"])
@with_error_code
def create_test_certificate(
	company: str | None = None, common_name: str | None = None, years: int = 3, replace: bool = False
) -> dict:
	"""A self-signed sealing certificate, used in the company's Sign Profile (System Manager)."""
	return certificates.create_test_certificate(company, common_name, years, bool(frappe.parse_json(replace)))


@frappe.whitelist(methods=["POST"])
@with_error_code
def upload_certificate(
	company: str,
	password: str,
	file_name: str = "seal.p12",
	content: str | None = None,
	kind: str = "CA-issued",
) -> dict:
	"""Make an uploaded PKCS#12 file the company's seal (System Manager). The file is multipart
	`file` or base64 `content`."""
	file_name, data = uploaded_file(file_name, content)
	return certificates.upload_certificate(company, file_name, data, password, kind)


@frappe.whitelist()
@with_error_code
def get_settings() -> dict:
	"""Everything the Settings page shows (Sign Manager and System Manager)."""
	return settings_page.overview()


@frappe.whitelist(methods=["POST"])
@with_error_code
def save_profile(company: str, values: dict | str) -> dict:
	return settings_page.save_profile(company, frappe.parse_json(values) or {})


@frappe.whitelist(methods=["POST"])
@with_error_code
def save_settings(section: str, values: dict | str) -> dict:
	return settings_page.save_settings(section, frappe.parse_json(values) or {})


@frappe.whitelist(methods=["POST"])
@with_error_code
def enable_doctype(doctype: str) -> dict:
	return settings_page.enable_doctype(doctype)


@frappe.whitelist(methods=["POST"])
@with_error_code
def disable_doctype(doctype: str) -> dict:
	settings_page.disable_doctype(doctype)
	return {"doctype": doctype}


@frappe.whitelist(methods=["POST"])
@with_error_code
def set_default_template(doctype: str, template: str | None = None) -> dict:
	return settings_page.set_default_template(doctype, template)


@frappe.whitelist()
@with_error_code
def doctype_choices(query: str = "") -> list:
	return settings_page.doctype_choices(query)


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


@frappe.whitelist()
@with_error_code
def list_templates() -> list:
	"""Templates for the staff Templates page, with when each was last used."""
	return template_catalog.list_templates()


@frappe.whitelist()
@with_error_code
def template_print_formats(doctype: str) -> list:
	"""The Print Formats of a DocType and whether each has signature fields."""
	return template_catalog.print_formats(doctype)


@frappe.whitelist()
@with_error_code
def template_doctype_fields(doctype: str) -> list:
	"""The fields of a DocType that a template's "Set a field" choice may write."""
	return template_catalog.doctype_fields(doctype)


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
	return uploaded_file(file_name, content)


def uploaded_file(file_name: str, content: str | None) -> tuple[str, bytes]:
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
def sendable_doctypes() -> list:
	"""The enabled DocTypes the user may send, with their template counts (send wizard)."""
	return pickers.sendable_doctypes()


@frappe.whitelist()
@with_error_code
def document_choices(doctype: str, query: str = "", limit: int = 20) -> list:
	"""Documents of an enabled DocType with party, date and total (send wizard)."""
	return pickers.document_choices(doctype, query, int(limit))


@frappe.whitelist()
@with_error_code
def search_people(query: str) -> list:
	"""Contacts and users matching the text, for the people step."""
	return pickers.search_people(query)


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
	"""List view: one envelope per selected document, queued as a Sign Bulk Run (jobs.bulk.run)."""
	return documents.queue_bulk_send(doctype, frappe.parse_json(names) or [], template)


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


# Number cards of the Signatures workspace. Frappe calls them with the card's filters.


@frappe.whitelist()
def card_awaiting_me(filters: str | None = None) -> dict:
	return cards.awaiting_me()


@frappe.whitelist()
def card_awaiting_others(filters: str | None = None) -> dict:
	return cards.awaiting_others()


@frappe.whitelist()
def card_completed_this_month(filters: str | None = None) -> dict:
	return cards.completed_this_month()


@frappe.whitelist()
def card_expiring_soon(filters: str | None = None) -> dict:
	return cards.expiring_soon()
