"""Jinja methods for Print Formats, such as the sign_field() anchor helper (DESIGN 4.2).

    {{ sign_field("signature", role="Customer", width=60, height=20) }}
    {{ sign_field("date_signed", role="Customer") }}
    {{ sign_field("company_stamp", role="Company", width=40, height=40, border=True) }}

Each call renders an inline-block of `width` x `height` mm with a [[fs:<role>:<field_type>:<n>]]
marker in 1pt white text at its top-left. `n` counts calls with the same role and field type in
one render, unless given. pdf/anchors.py finds the markers in the rendered PDF.
"""

import frappe
from frappe import _
from markupsafe import Markup, escape

from frappe_sign.pdf.anchors import DEFAULT_SIZES_MM, field_type_token, marker, role_token
from frappe_sign.pdf.source import declare_anchor, next_anchor_number

MAX_SIZE_MM = 400.0


def sign_field(
	field_type: str,
	role: str,
	width: float | None = None,
	height: float | None = None,
	n: int | None = None,
	border: bool = False,
) -> Markup:
	try:
		type_token, role_label = field_type_token(field_type), role_token(role)
	except ValueError as error:
		frappe.throw(_("sign_field(): {0}").format(str(error)), title=_("Print Format error"))
	default_width, default_height = DEFAULT_SIZES_MM[type_token]
	width_mm, height_mm = size(width, default_width), size(height, default_height)
	number = int(n) if n else next_anchor_number(role_label, type_token)
	tag = marker(role_label, type_token, number)
	declare_anchor(tag, width_mm, height_mm)
	outline = "border:1px dotted #9ca3af;" if border else ""
	return Markup(
		'<span class="frappe-sign-field" style="display:inline-block;position:relative;'
		f"box-sizing:border-box;vertical-align:bottom;width:{width_mm}mm;height:{height_mm}mm;{outline}"
		'"><span style="position:absolute;top:0;left:0;font-size:1pt;line-height:1;color:#ffffff;'
		f'white-space:nowrap;">{escape(tag)}</span></span>'
	)


def size(value: float | None, default: float) -> float:
	if value is None or value == "":
		return default
	number = float(value)
	if not 0 < number <= MAX_SIZE_MM:
		frappe.throw(
			_("sign_field(): sizes are in mm, above 0 and at most {0}.").format(int(MAX_SIZE_MM)),
			title=_("Print Format error"),
		)
	return number
