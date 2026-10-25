"""Stage 3: locate [[fs:<role>:<field_type>:<n>]] markers and build normalized rects (DESIGN 4.2).

sign_field() (frappe_sign/jinja) renders an inline-block of the declared size in mm, with the marker
in 1pt white text at its top-left. pypdf's text visitor reports each marker with the matrices at
its first glyph. The marker's top is the field's top-left corner; the field size is the declared
size, scaled by how much the generator scaled the 1pt marker, so a Print Format that zooms its
content still gets rects that match the drawn box.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass

from pypdf._page import PageObject
from pypdf.errors import PyPdfError

from frappe_sign.pdf.pages import metric_of, open_pdf
from frappe_sign.pdf.types import Anchor, PageMetric, PdfInvalid, Rect, user_to_display

MARKER_PT = 1.0
MM = 72 / 25.4
# Share of the font size between the marker's top and its baseline (line-height 1).
MARKER_ASCENT = 0.8
# A marker drawn far from 1pt was resized by the generator (minimum font size); ignore that scale.
SCALE_RANGE = (0.5, 2.0)
# Marker field type -> Sign Template Field type.
FIELD_TYPES = {
	"signature": "Signature",
	"initials": "Initials",
	"company_stamp": "Company Stamp",
	"full_name": "Full Name",
	"email": "Email",
	"date_signed": "Date Signed",
	"text": "Text",
	"number": "Number",
	"checkbox": "Checkbox",
	"dropdown": "Dropdown",
}
# Width and height in mm when sign_field() is called without them.
DEFAULT_SIZES_MM = {
	"signature": (60.0, 20.0),
	"initials": (25.0, 15.0),
	"company_stamp": (40.0, 40.0),
	"full_name": (60.0, 8.0),
	"email": (60.0, 8.0),
	"date_signed": (40.0, 8.0),
	"text": (60.0, 8.0),
	"number": (30.0, 8.0),
	"checkbox": (6.0, 6.0),
	"dropdown": (40.0, 8.0),
}
ROLE_TOKEN = re.compile(r"[A-Za-z0-9_-]+")
MARKER = re.compile(r"\[\[fs:([A-Za-z0-9_-]+):([a-z_]+):(\d+)\]\]")

# PDF matrix [a b c d e f].
Matrix = tuple[float, float, float, float, float, float]


@dataclass(frozen=True)
class TextRun:
	"""Text that pypdf reported with one matrix: its first glyph's origin and effective size."""

	text: str
	matrix: Matrix
	font_size: float


def role_token(role: str) -> str:
	"""The role as written in a marker: spaces become underscores. Raises ValueError otherwise."""
	token = "_".join(str(role or "").split())
	if not ROLE_TOKEN.fullmatch(token):
		raise ValueError(f"Role {role!r} must use Latin letters, digits, spaces, - or _")
	return token


def field_type_token(field_type: str) -> str:
	"""`signature`, `Date Signed` or `date_signed` -> `date_signed`. Raises ValueError if unknown."""
	token = "_".join(str(field_type or "").lower().split())
	if token not in FIELD_TYPES:
		raise ValueError(f"{field_type!r} is not a field type; use one of {', '.join(FIELD_TYPES)}")
	return token


def marker(role: str, field_type: str, n: int) -> str:
	return f"[[fs:{role_token(role)}:{field_type_token(field_type)}:{int(n)}]]"


def find_anchors(pdf: bytes, sizes: Mapping[str, tuple[float, float]] | None = None) -> list[Anchor]:
	"""Every marker in the PDF, first occurrence per tag, in page order.

	`sizes` maps a marker to the width and height in mm that sign_field() declared; markers
	without one take the default size of their field type.
	"""
	reader = open_pdf(pdf)
	found: dict[str, Anchor] = {}
	try:
		for number, page in enumerate(reader.pages, start=1):
			metric = metric_of(page, number)
			for run in text_runs(page):
				for anchor in anchors_in(run, metric, sizes or {}):
					found.setdefault(anchor.tag, anchor)
	except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as error:
		raise PdfInvalid(f"Not a readable PDF: {error}") from error
	return list(found.values())


def text_runs(page: PageObject) -> list[TextRun]:
	runs: list[TextRun] = []

	def visit(text: str, cm: list[float], tm: list[float], font: object, font_size: float) -> None:
		if "[[fs:" in "".join(text.split()):
			runs.append(TextRun(text, multiply(tm, cm), float(font_size or 0)))

	page.extract_text(visitor_text=visit)
	return runs


def anchors_in(run: TextRun, metric: PageMetric, sizes: Mapping[str, tuple[float, float]]) -> list[Anchor]:
	compact = "".join(run.text.split())
	scale = run_scale(run)
	anchors = []
	for match in MARKER.finditer(compact):
		role, field_type, n = match.group(1), match.group(2), int(match.group(3))
		if field_type not in FIELD_TYPES:
			continue
		tag = match.group(0)
		# Glyphs before the marker in the same run: about half an em each.
		advance = match.start() * 0.5 * run.font_size
		top_left = apply(run.matrix, advance, MARKER_ASCENT * run.font_size)
		width_mm, height_mm = sizes.get(tag) or DEFAULT_SIZES_MM[field_type]
		anchors.append(
			Anchor(
				tag=tag,
				role=role,
				field_type=FIELD_TYPES[field_type],
				n=n,
				page=metric.page,
				rect=display_rect(metric, top_left, width_mm * MM * scale, height_mm * MM * scale),
			)
		)
	return anchors


def run_scale(run: TextRun) -> float:
	"""How much the generator scaled the 1pt marker: effective font size over 1pt."""
	a, b, c, d = run.matrix[:4]
	effective = run.font_size * math.sqrt(abs(a * d - b * c))
	scale = effective / MARKER_PT
	return scale if SCALE_RANGE[0] <= scale <= SCALE_RANGE[1] else 1.0


def display_rect(metric: PageMetric, top_left: tuple[float, float], width: float, height: float) -> Rect:
	"""A normalized rect from a user space top-left point and a size in points, kept on the page."""
	x, y = user_to_display(metric, *top_left)
	page_width, page_height = metric.display_width, metric.display_height
	x, y = min(max(x, 0.0), page_width), min(max(y, 0.0), page_height)
	width, height = min(width, page_width - x), min(height, page_height - y)
	return Rect(x / page_width, y / page_height, width / page_width, height / page_height)


def multiply(m: list[float], n: list[float]) -> Matrix:
	"""m x n for PDF matrices: apply m, then n."""
	return (
		m[0] * n[0] + m[1] * n[2],
		m[0] * n[1] + m[1] * n[3],
		m[2] * n[0] + m[3] * n[2],
		m[2] * n[1] + m[3] * n[3],
		m[4] * n[0] + m[5] * n[2] + n[4],
		m[4] * n[1] + m[5] * n[3] + n[5],
	)


def apply(m: Matrix, x: float, y: float) -> tuple[float, float]:
	return (x * m[0] + y * m[2] + m[4], x * m[1] + y * m[3] + m[5])
