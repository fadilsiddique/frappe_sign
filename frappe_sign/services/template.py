"""Templates: create, update, upload PDF, publish an immutable Sign Template Version."""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.types import PdfError
from frappe_sign.services import settings
from frappe_sign.services.errors import raise_pdf_error
from frappe_sign.utils.files import new_private_file, read_file_url
from frappe_sign.utils.hashing import sha256_hex

UPLOADED_PDF = "Uploaded PDF"
EDITABLE_FIELDS = frozenset(
	{
		"title",
		"company",
		"is_active",
		"source_type",
		"reference_doctype",
		"print_format",
		"letter_head",
		"signing_order",
		"otp_mode",
		"email_template",
		"expiry_days",
		"reminder_days",
		"post_sign_action",
		"post_sign_config",
		"roles",
		"fields",
	}
)
SNAPSHOT_FIELDS = (
	"title",
	"company",
	"source_type",
	"reference_doctype",
	"print_format",
	"letter_head",
	"pdf_file",
	"page_metrics",
	"signing_order",
	"otp_mode",
	"email_template",
	"expiry_days",
	"reminder_days",
	"post_sign_action",
	"post_sign_config",
)
ROLE_FIELDS = (
	"role_label",
	"routing_order",
	"kind",
	"signer_source",
	"source_field",
	"fixed_user",
	"can_delegate",
	"color",
)
FIELD_FIELDS = (
	"field_key",
	"role_label",
	"field_type",
	"page",
	"x",
	"y",
	"w",
	"h",
	"anchor_tag",
	"required",
	"read_only",
	"prefill_path",
	"options",
	"font_size",
	"validation_regex",
)
SIGNING_KINDS = ("Signer", "Approver")


def create_template(data: dict[str, Any]) -> Any:
	doc = frappe.get_doc({"doctype": "Sign Template", **editable(data)})
	return doc.insert()


def update_template(name: str, data: dict[str, Any]) -> Any:
	doc = frappe.get_doc("Sign Template", name)
	doc.check_permission("write")
	doc.update(editable(data))
	return doc.save()


def editable(data: dict[str, Any]) -> dict[str, Any]:
	"""Only fields a user may set; the PDF, its metrics and the published version are service-owned."""
	return {key: value for key, value in data.items() if key in EDITABLE_FIELDS}


def upload_pdf(template: str, file_name: str, content: bytes) -> list[dict[str, Any]]:
	"""Sanitize an uploaded PDF, attach it privately to the template and store its page metrics."""
	doc = frappe.get_doc("Sign Template", template)
	doc.check_permission("write")
	try:
		clean = sanitize(content, max_bytes=settings.max_upload_bytes(), max_pages=settings.max_pages())
	except PdfError as error:
		raise_pdf_error(error)
	file = new_private_file(clean.data, file_name, "Sign Template", template).insert()
	metrics = [metric.to_dict() for metric in clean.metrics]
	doc.pdf_file = file.file_url
	doc.page_metrics = json.dumps(metrics)
	doc.save()
	return metrics


def publish(template: str) -> Any:
	doc = frappe.get_doc("Sign Template", template)
	doc.check_permission("write")
	frappe.has_permission("Sign Template Version", "create", throw=True)
	check_publishable(doc)
	source_sha256 = sha256_hex(read_file_url(doc.pdf_file)) if doc.source_type == UPLOADED_PDF else None
	last = frappe.db.get_value(
		"Sign Template Version", {"template": template}, "version_no", order_by="version_no desc"
	)
	version = frappe.get_doc(
		{
			"doctype": "Sign Template Version",
			"template": template,
			"version_no": cint(last) + 1,
			"snapshot": json.dumps(snapshot(doc), sort_keys=True),
			"source_sha256": source_sha256,
			"published_by": frappe.session.user,
			"published_on": now_datetime(),
		}
	).insert()
	doc.db_set("published_version", version.name)
	return version


def snapshot(doc: Any) -> dict[str, Any]:
	data = {field: doc.get(field) for field in SNAPSHOT_FIELDS}
	data["roles"] = [{field: role.get(field) for field in ROLE_FIELDS} for role in doc.roles]
	data["fields"] = [{field: row.get(field) for field in FIELD_FIELDS} for row in doc.fields]
	return data


def check_publishable(doc: Any) -> None:
	if not any(role.kind in SIGNING_KINDS for role in doc.roles):
		frappe.throw(_("Add at least one Signer or Approver role before publishing."), FieldValidationError)
	if doc.source_type != UPLOADED_PDF:
		return
	if not doc.pdf_file or not doc.page_metrics:
		frappe.throw(_("Upload the PDF before publishing."), FieldValidationError)
	pages = len(json.loads(doc.page_metrics))
	for field in doc.fields:
		if cint(field.page) > pages:
			frappe.throw(
				_("Field {0} is on page {1}, but the PDF has {2} pages.").format(
					field.field_key, field.page, pages
				),
				FieldValidationError,
			)


def load_snapshot(version: str) -> dict[str, Any]:
	return json.loads(frappe.db.get_value("Sign Template Version", version, "snapshot") or "{}")
