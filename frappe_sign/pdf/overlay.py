"""Stage 4: draw field values and captures with reportlab and merge them into the pages.

Each page with fields gets one reportlab canvas at the page's display size, drawn upright as a
reader sees it. The canvas is merged with pdf/types.display_matrix, which maps it onto the page's
user space through the CropBox and /Rotate.
"""

from __future__ import annotations

import io
from collections import defaultdict

from PIL import Image
from pypdf import PdfReader, PdfWriter, Transformation
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from frappe_sign.pdf.pages import metric_of, open_pdf
from frappe_sign.pdf.text import FontNames, Run, is_rtl, register_fonts, runs_width, visual_runs
from frappe_sign.pdf.types import FontSet, PageMetric, PdfInvalid, PlacedField, display_matrix

IMAGE_TYPES = frozenset({"Signature", "Initials", "Company Stamp"})
SKIPPED_TYPES = frozenset({"Attachment"})
CHECKED_VALUES = frozenset({"1", "true", "yes", "on", "checked"})
MIN_FONT_SIZE = 4.0
TEXT_PADDING = 2.0
# The white mask reaches this far past the field, so no anti-aliased edge of what it hides shows.
MASK_BLEED = 0.5
INK = (0.07, 0.09, 0.15)

# Canvas space for one field: left, bottom, width, height in points, y up.
Area = tuple[float, float, float, float]


def apply_fields(pdf: bytes, fields: list[PlacedField], captures: dict[str, bytes], fonts: FontSet) -> bytes:
	reader = open_pdf(pdf)
	writer = PdfWriter(clone_from=reader)
	names = register_fonts(fonts)
	by_page: dict[int, list[PlacedField]] = defaultdict(list)
	for placed in fields:
		if placed.page < 1 or placed.page > len(writer.pages):
			raise PdfInvalid(f"Field {placed.key} is on page {placed.page}; the PDF has {len(writer.pages)}")
		by_page[placed.page].append(placed)
	for number in sorted(by_page):
		page = writer.pages[number - 1]
		metric = metric_of(page, number)
		overlay = PdfReader(io.BytesIO(draw_page(metric, by_page[number], captures, names))).pages[0]
		page.merge_transformed_page(overlay, Transformation(display_matrix(metric)))
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


def draw_page(
	metric: PageMetric, fields: list[PlacedField], captures: dict[str, bytes], names: FontNames
) -> bytes:
	buffer = io.BytesIO()
	width, height = metric.display_width, metric.display_height
	pdf = canvas.Canvas(buffer, pagesize=(width, height), invariant=1, pageCompression=1)
	for placed in fields:
		rect = placed.rect
		area = (rect.x * width, (1 - rect.y - rect.h) * height, rect.w * width, rect.h * height)
		if placed.mask:
			left, bottom, field_width, field_height = area
			pdf.setFillColorRGB(1, 1, 1)
			pdf.rect(
				left - MASK_BLEED,
				bottom - MASK_BLEED,
				field_width + 2 * MASK_BLEED,
				field_height + 2 * MASK_BLEED,
				stroke=0,
				fill=1,
			)
		draw_field(pdf, placed, area, captures, names)
	pdf.showPage()
	pdf.save()
	return buffer.getvalue()


def draw_field(
	pdf: canvas.Canvas, placed: PlacedField, area: Area, captures: dict[str, bytes], names: FontNames
) -> None:
	if placed.field_type in SKIPPED_TYPES:
		return
	if placed.field_type in IMAGE_TYPES:
		if placed.key in captures:
			draw_image(pdf, captures[placed.key], area, placed.key)
	elif placed.field_type == "Checkbox":
		draw_checkbox(pdf, (placed.value or "").strip().lower() in CHECKED_VALUES, area)
	elif placed.value:
		draw_text(pdf, placed.value, placed.font_size, area, names)


def draw_image(pdf: canvas.Canvas, data: bytes, area: Area, key: str) -> None:
	"""Fit the image inside the area, keeping its aspect ratio, centred."""
	try:
		with Image.open(io.BytesIO(data)) as probe:
			probe.verify()
	except (OSError, SyntaxError, ValueError) as error:
		raise PdfInvalid(f"Capture for field {key} is not a readable image") from error
	image = ImageReader(io.BytesIO(data))
	image_width, image_height = image.getSize()
	left, bottom, width, height = area
	scale = min(width / image_width, height / image_height)
	drawn_width, drawn_height = image_width * scale, image_height * scale
	pdf.drawImage(
		image,
		left + (width - drawn_width) / 2,
		bottom + (height - drawn_height) / 2,
		drawn_width,
		drawn_height,
		mask="auto",
	)


def draw_checkbox(pdf: canvas.Canvas, checked: bool, area: Area) -> None:
	left, bottom, width, height = area
	side = min(width, height) * 0.9
	x, y = left + (width - side) / 2, bottom + (height - side) / 2
	pdf.setStrokeColorRGB(*INK)
	pdf.setLineWidth(max(0.75, side * 0.06))
	pdf.rect(x, y, side, side, stroke=1, fill=0)
	if checked:
		pdf.setLineWidth(max(1.0, side * 0.12))
		pdf.setLineCap(1)
		pdf.setLineJoin(1)
		path = pdf.beginPath()
		path.moveTo(x + side * 0.2, y + side * 0.5)
		path.lineTo(x + side * 0.42, y + side * 0.25)
		path.lineTo(x + side * 0.8, y + side * 0.78)
		pdf.drawPath(path, stroke=1, fill=0)


def vertical_metrics(names: FontNames) -> tuple[float, float]:
	"""Ascent minus descent, and descent, of the Latin font as shares of the font size."""
	font = pdfmetrics.getFont(names.latin)
	assert isinstance(font, TTFont)
	ascent, descent = float(font.face.ascent) / 1000, float(font.face.descent) / 1000
	return ascent - descent, descent


def fit_font_size(
	runs: list[Run], fonts: FontSet, max_size: float, box_width: float, box_height: float
) -> float:
	"""The largest size up to `max_size` at which the runs fit on one line inside the box."""
	return fitted_size(runs, register_fonts(fonts), max_size, box_width, box_height)


def fitted_size(
	runs: list[Run], names: FontNames, max_size: float, box_width: float, box_height: float
) -> float:
	size = min(max_size, box_height / vertical_metrics(names)[0])
	available = max(box_width - 2 * TEXT_PADDING, 1.0)
	width = runs_width(runs, names, size)
	if width > available:
		size = size * available / width
	return max(MIN_FONT_SIZE, round(size, 2))


def draw_text(pdf: canvas.Canvas, value: str, font_size: float, area: Area, names: FontNames) -> None:
	left, bottom, width, height = area
	runs = visual_runs(value)
	size = fitted_size(runs, names, font_size, width, height)
	text_width = runs_width(runs, names, size)
	line_height, descent = vertical_metrics(names)
	baseline = bottom + (height - line_height * size) / 2 - descent * size
	x = left + width - TEXT_PADDING - text_width if is_rtl(value) else left + TEXT_PADDING
	pdf.setFillColorRGB(*INK)
	for text, arabic in runs:
		font = names.arabic if arabic else names.latin
		pdf.setFont(font, size)
		pdf.drawString(x, baseline, text)
		x += pdfmetrics.stringWidth(text, font, size)
