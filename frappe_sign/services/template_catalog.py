"""What the staff Templates page and the Print Format template editor read (U.7).

Reads follow the user's permissions (frappe.get_list). Nothing here writes: saving and publishing
stay in services/template.py.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.query_builder.functions import Max
from frappe.utils import now_datetime, time_diff_in_seconds

SIGN_FIELD_CALL = "sign_field("


def list_templates() -> list[dict[str, Any]]:
	"""Active and inactive templates, newest edit first, each with when a request last used it."""
	rows = frappe.get_list(
		"Sign Template",
		fields=[
			"name",
			"title",
			"source_type",
			"reference_doctype",
			"print_format",
			"pdf_file",
			"published_version",
			"is_active",
			"modified",
		],
		order_by="modified desc",
		limit=200,
	)
	last_used = last_used_by_template([row.name for row in rows])
	now = now_datetime()
	return [
		{
			**row,
			"last_used": last_used.get(row.name),
			# Seconds, so the browser's time zone never shifts "3 hours ago".
			"last_used_seconds": time_diff_in_seconds(now, last_used[row.name])
			if row.name in last_used
			else None,
		}
		for row in rows
	]


def last_used_by_template(templates: list[str]) -> dict[str, Any]:
	if not templates:
		return {}
	version, envelope = frappe.qb.DocType("Sign Template Version"), frappe.qb.DocType("Sign Envelope")
	rows = (
		frappe.qb.from_(envelope)
		.join(version)
		.on(envelope.template_version == version.name)
		.select(version.template, Max(envelope.creation).as_("last_used"))
		.where(version.template.isin(templates))
		.groupby(version.template)
		.run(as_dict=True)
	)
	return {row.template: row.last_used for row in rows}


def print_formats(doctype: str) -> list[dict[str, Any]]:
	"""The enabled Print Formats of a DocType, each flagged when its HTML calls sign_field().
	Formats kept as files (standard ones) have no HTML in the database, so they read as "no"."""
	rows = frappe.get_list(
		"Print Format",
		filters={"doc_type": doctype, "disabled": 0},
		fields=["name", "html"],
		order_by="name asc",
		limit=100,
	)
	return [{"name": row.name, "has_sign_fields": SIGN_FIELD_CALL in (row.html or "")} for row in rows]


def doctype_fields(doctype: str) -> list[dict[str, str]]:
	"""The fields a post-sign "Set a field" may write: editable, not layout or table fields."""
	frappe.has_permission(doctype, "read", throw=True)
	skip = set(frappe.model.no_value_fields) | set(frappe.model.table_fields)
	return [
		{"fieldname": df.fieldname, "label": df.label or df.fieldname}
		for df in frappe.get_meta(doctype).fields
		if df.fieldtype not in skip and not df.read_only and not df.hidden
	]
