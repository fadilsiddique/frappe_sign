"""Guards that DocType controllers share for the integrity rules (DESIGN 2.6).

Controllers call these from `before_validate`, not `validate`: `flags.ignore_validate` skips
`validate` but not `before_validate`, so a guard there cannot be switched off by a flag.
"""

import re

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, get_datetime

from frappe_sign.exceptions import FieldValidationError, ImmutableRecord
from frappe_sign.utils.hashing import is_sha256_hex
from frappe_sign.utils.paths import is_private_file_url

# Float columns hold 9 decimals; allow that much rounding at the page edge.
RECT_TOLERANCE = 1e-9


def reject_update(doc) -> None:
	"""Insert-only records (Sign Event, Sign Capture, Sign Template Version) never change."""
	if not doc.is_new():
		frappe.throw(
			_("{0} {1} is insert-only and cannot be changed.").format(_(doc.doctype), doc.name),
			ImmutableRecord,
		)


def reject_delete(doc) -> None:
	frappe.throw(
		_("{0} {1} is insert-only and cannot be deleted.").format(_(doc.doctype), doc.name),
		ImmutableRecord,
	)


def require_sha256(doc, *fieldnames: str) -> None:
	"""Tokens, session secrets, OTPs and file hashes are stored only as SHA-256 hex digests."""
	for fieldname in fieldnames:
		value = doc.get(fieldname)
		if value and not is_sha256_hex(value):
			frappe.throw(
				_("{0} must be a SHA-256 hex digest.").format(_(doc.meta.get_label(fieldname))),
				FieldValidationError,
			)


def require_private_files(doc, *fieldnames: str) -> None:
	for fieldname in fieldnames:
		file_url = doc.get(fieldname)
		if file_url and not is_private_file_url(file_url):
			frappe.throw(
				_("{0} must be a private file.").format(_(doc.meta.get_label(fieldname))),
				FieldValidationError,
			)


def changed_fields(doc, before, fieldnames: tuple[str, ...]) -> list[str]:
	"""Fields whose value differs between `doc` and `before`, ignoring str/date/number form."""
	return [
		fieldname
		for fieldname in fieldnames
		if not _same_value(doc.get(fieldname), before.get(fieldname), doc.meta.get_field(fieldname).fieldtype)
	]


def _same_value(value, other, fieldtype: str) -> bool:
	if fieldtype in ("Check", "Int"):
		return cint(value) == cint(other)
	if fieldtype == "Float":
		return flt(value) == flt(other)
	if fieldtype in ("Date", "Datetime"):
		return (get_datetime(value) if value else None) == (get_datetime(other) if other else None)
	return cstr(value) == cstr(other)


def is_normalized_rect(x: float, y: float, w: float, h: float) -> bool:
	"""x, y, w, h in 0..1 with a top-left origin, inside the visible page box (D7)."""
	return (
		x >= 0 and y >= 0 and w > 0 and h > 0 and x + w <= 1 + RECT_TOLERANCE and y + h <= 1 + RECT_TOLERANCE
	)


def validate_placed_field(row) -> None:
	"""Shape checks for a Sign Template Field or Sign Envelope Field row."""
	name = row.field_key or _("row {0}").format(row.idx)
	page = cint(row.page)
	if page < 0:
		frappe.throw(_("Field {0}: page cannot be negative.").format(name), FieldValidationError)
	if page == 0 and not row.anchor_tag:
		frappe.throw(
			_("Field {0}: page 0 means the position comes from an anchor, so set an anchor tag.").format(
				name
			),
			FieldValidationError,
		)
	if page > 0 and not is_normalized_rect(flt(row.x), flt(row.y), flt(row.w), flt(row.h)):
		frappe.throw(
			_(
				"Field {0}: x, y, width and height must place the field inside the page (0 to 1), with a width and height above 0."
			).format(name),
			FieldValidationError,
		)
	if row.field_type == "Dropdown" and not cstr(row.options).strip():
		frappe.throw(_("Field {0}: a Dropdown needs options.").format(name), FieldValidationError)
	if flt(row.font_size) <= 0:
		frappe.throw(_("Field {0}: font size must be above 0.").format(name), FieldValidationError)
	if row.validation_regex:
		try:
			re.compile(row.validation_regex)
		except re.error as error:
			frappe.throw(
				_("Field {0}: validation regex is not valid ({1}).").format(name, str(error)),
				FieldValidationError,
			)
