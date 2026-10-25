"""Preview a Print Format source in the send wizard (DESIGN 8.1, P2.9).

preview_source renders the document in the request (the one render outside a job besides
signing.finish, kept short by the 5 minute cache), sanitizes it as the send job would and returns
the anchors sign_field() placed. The PDF stays in the cache under a key bound to the user;
preview_pdf streams it. A Print Format with a generator other than wkhtmltopdf or chrome renders,
but its anchors are untested (ARCHITECTURE, Compatibility), so the result says so.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.pdf.anchors import find_anchors
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.source import TESTED_GENERATORS, render
from frappe_sign.pdf.types import PdfError
from frappe_sign.services import settings
from frappe_sign.services.envelope import prefill_value
from frappe_sign.services.errors import pdf_message
from frappe_sign.services.template import load_snapshot
from frappe_sign.utils.hashing import sha256_hex

CACHE_PREFIX = "frappe_sign::preview::"
CACHE_SECONDS = 300


def preview_source(
	doctype: str, name: str, print_format: str | None = None, letter_head: str | None = None
) -> dict[str, Any]:
	doc = frappe.get_doc(doctype, name)
	doc.check_permission("print")
	user = frappe.session.user
	key = sha256_hex(f"{user}|{doctype}|{name}|{print_format}|{letter_head}|{doc.modified}")
	cached = frappe.cache.get_value(CACHE_PREFIX + key)
	if not cached:
		try:
			rendered = render(doctype, name, print_format, letter_head)
			clean = sanitize(
				rendered.pdf, max_bytes=settings.max_upload_bytes(), max_pages=settings.max_pages()
			)
			anchors = find_anchors(clean.data, rendered.declared)
		except PdfError as error:
			throw(FieldValidationError, pdf_message(error))
		cached = {
			"user": user,
			"pdf": clean.data,
			"generator": rendered.generator,
			"metrics": [metric.to_dict() for metric in clean.metrics],
			"anchors": [
				{
					"tag": anchor.tag,
					"role": anchor.role,
					"field_type": anchor.field_type,
					"n": anchor.n,
					"page": anchor.page,
					"x": anchor.rect.x,
					"y": anchor.rect.y,
					"w": anchor.rect.w,
					"h": anchor.rect.h,
				}
				for anchor in anchors
			],
		}
		frappe.cache.set_value(CACHE_PREFIX + key, cached, expires_in_sec=CACHE_SECONDS)
	return {
		"key": key,
		"generator": cached["generator"],
		"generator_tested": cached["generator"] in TESTED_GENERATORS,
		"metrics": cached["metrics"],
		"anchors": cached["anchors"],
	}


def preview_pdf(key: str) -> bytes:
	"""The previewed PDF, only for the user who rendered it."""
	cached = frappe.cache.get_value(CACHE_PREFIX + (key or ""))
	if not cached or cached.get("user") != frappe.session.user:
		throw(FieldValidationError, _("The preview has expired. Load it again."))
	return cached["pdf"]


def preview_prefill(template: str, doctype: str, name: str) -> list[dict[str, Any]]:
	"""The values the template's prefilled fields would take from the document."""
	frappe.has_permission("Sign Template", "read", doc=template, throw=True)
	version = frappe.db.get_value("Sign Template", template, "published_version")
	if not version:
		return []
	source = frappe.get_doc(doctype, name)
	source.check_permission("read")
	return [
		{
			"field_key": field["field_key"],
			"role_label": field["role_label"],
			"field_type": field["field_type"],
			"read_only": field.get("read_only"),
			"value": prefill_value(field["prefill_path"], source),
		}
		for field in load_snapshot(version).get("fields") or []
		if field.get("prefill_path")
	]
