"""Designer round trip, server half (P1.16).

frontend/tests/designer-roundtrip.test.ts places and drags fields in the designer store and writes
the saved payload, with each field's on-screen pixel rect, to tests/fixtures/designer_roundtrip.json.
Here the payload is saved through the template service (as api.staff.save_template does), read back
from the database, drawn by the server overlay and rendered by pdfium at the designer's viewport
width. Every field must land on the pixels where the designer showed it.
"""

import io
import json
from pathlib import Path

import frappe
import pypdfium2 as pdfium
from PIL import Image, ImageChops

from frappe_sign.pdf.overlay import apply_fields
from frappe_sign.pdf.text import default_fonts
from frappe_sign.pdf.types import PlacedField, Rect
from frappe_sign.services import template as template_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf
from frappe_sign.utils.files import read_file_url

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "designer_roundtrip.json"
MAGENTA = (255, 0, 255)
# The rendered box is found in whole pixels and its anti-aliased edge pixels count, while the
# designer's rect is fractional: allow rounding plus one edge pixel.
TOLERANCE_PX = 1.5


def solid(width: float, height: float) -> bytes:
	out = io.BytesIO()
	Image.new("RGB", (max(1, round(width * 8)), max(1, round(height * 8))), MAGENTA).save(out, "PNG")
	return out.getvalue()


def magenta_box(image: Image.Image) -> tuple[int, int, int, int] | None:
	red, green, blue = image.split()
	mask = ImageChops.multiply(
		ImageChops.multiply(
			red.point(lambda v: 255 if v > 200 else 0), green.point(lambda v: 255 if v < 60 else 0)
		),
		blue.point(lambda v: 255 if v > 200 else 0),
	)
	return mask.getbbox()


class TestDesignerRoundTrip(SignTestCase):
	def test_fields_land_where_the_designer_showed_them(self):
		cases = json.loads(FIXTURE.read_text())["cases"]
		self.assertEqual(len(cases), 3)
		for case in cases:
			with self.subTest(file=case["file"]):
				self.check_case(case)

	def check_case(self, case: dict) -> None:
		payload = {**case["payload"], "source_type": "Uploaded PDF"}
		template = template_service.create_template(payload)
		template_service.upload_pdf(template.name, case["file"], fixture_pdf(case["file"]))
		version = template_service.publish(template.name)
		saved = json.loads(version.snapshot)
		pdf = read_file_url(saved["pdf_file"])
		viewport = case["viewport"]
		for field in saved["fields"]:
			screen_x, screen_y, screen_w, screen_h = case["screen"][field["field_key"]]
			placed = PlacedField(
				key=field["field_key"],
				field_type="Signature",
				page=field["page"],
				rect=Rect(field["x"], field["y"], field["w"], field["h"]),
			)
			drawn = apply_fields(pdf, [placed], {placed.key: solid(screen_w, screen_h)}, default_fonts())
			document = pdfium.PdfDocument(drawn)
			try:
				page = document[0]
				scale = viewport["width"] / page.get_width()
				image = page.render(scale=scale).to_pil().convert("RGB")
			finally:
				document.close()
			self.assertAlmostEqual(image.size[0], viewport["width"], delta=1)
			box = magenta_box(image)
			self.assertIsNotNone(box, field["field_key"])
			expected = (screen_x, screen_y, screen_x + screen_w, screen_y + screen_h)
			for actual, wanted in zip(box, expected, strict=True):
				self.assertLessEqual(
					abs(actual - wanted),
					TOLERANCE_PX,
					f"{case['file']} {field['field_key']}: {box} vs {expected}",
				)
		frappe.db.rollback()
