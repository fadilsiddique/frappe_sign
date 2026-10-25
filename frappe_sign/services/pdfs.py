"""The envelope's PDF with the values filled so far: used for intermediate PDFs and the final seal."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cint, flt

from frappe_sign.pdf.overlay import apply_fields
from frappe_sign.pdf.text import default_fonts
from frappe_sign.pdf.types import PlacedField, Rect
from frappe_sign.utils.files import read_file

IMAGE_TYPES = ("Signature", "Initials", "Company Stamp")


def placed_fields(envelope: Any) -> tuple[list[PlacedField], dict[str, bytes]]:
	"""Every filled field of the envelope, and the capture images keyed by field_key."""
	fields: list[PlacedField] = []
	captures: dict[str, bytes] = {}
	for row in envelope.fields:
		if row.field_type in IMAGE_TYPES:
			if not row.capture:
				continue
			image = frappe.db.get_value("Sign Capture", row.capture, "image")
			file_name = frappe.db.get_value(
				"File", {"file_url": image, "attached_to_name": envelope.name}, "name"
			)
			captures[row.field_key] = read_file(file_name)
		elif not row.value:
			continue
		fields.append(
			PlacedField(
				key=row.field_key,
				field_type=row.field_type,
				page=cint(row.page),
				rect=Rect(flt(row.x), flt(row.y), flt(row.w), flt(row.h)),
				value=row.value,
				font_size=flt(row.font_size) or 11.0,
				mask=bool(row.anchor_tag),
			)
		)
	return fields, captures


def filled_pdf(envelope: Any) -> bytes:
	"""The frozen original with every value saved so far drawn on it."""
	fields, captures = placed_fields(envelope)
	return apply_fields(read_file(envelope.original_file), fields, captures, default_fonts())


def current_pdf_file(envelope: Any) -> str:
	"""File name of the PDF a signer sees: the latest intermediate, or the original (DESIGN 5.2)."""
	finished = [row for row in envelope.recipients if row.intermediate_file and row.signed_on]
	if finished:
		return max(finished, key=lambda row: row.signed_on).intermediate_file
	return envelope.original_file
