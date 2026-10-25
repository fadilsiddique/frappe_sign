"""pdf/overlay.py (P1.3): field values, captures and Arabic text drawn onto the pages.

Positions are checked against an independent renderer: pdfium rasterizes the result and each
field is found again by colour, as check_coords.py does for coords.json. Visual snapshots compare
the rasterized page with golden PNGs in tests/fixtures/golden/. Regenerate them after an intended
change with FRAPPE_SIGN_UPDATE_GOLDEN=1 and review the new images before committing.
"""

import io
import json
import os
from pathlib import Path

import arabic_reshaper
import pypdfium2 as pdfium
from bidi.algorithm import get_display
from frappe.tests import UnitTestCase
from PIL import Image, ImageChops, ImageDraw
from pypdf import PdfReader

from frappe_sign.pdf.overlay import apply_fields, fit_font_size
from frappe_sign.pdf.text import default_fonts, has_arabic, is_rtl, visual_runs
from frappe_sign.pdf.types import PdfInvalid, PlacedField, Rect

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
PDFS = FIXTURES / "pdfs"
GOLDEN = FIXTURES / "golden"
COORDS = json.loads((FIXTURES / "coords.json").read_text())["fixtures"]
UPDATE_GOLDEN = os.environ.get("FRAPPE_SIGN_UPDATE_GOLDEN") == "1"

ARABIC_NAME = "أحمد خان"
MIXED_NAME = "Ahmed Khan أحمد"
MAGENTA = (255, 0, 255)
SCALE = 2
# Share of pixels allowed to differ from the golden image (anti-aliasing across platforms).
GOLDEN_TOLERANCE = 0.005


def fixture(name: str) -> bytes:
	return (PDFS / name).read_bytes()


def solid_png(width: int, height: int, colour=MAGENTA) -> bytes:
	out = io.BytesIO()
	Image.new("RGB", (width, height), colour).save(out, "PNG")
	return out.getvalue()


def signature_png() -> bytes:
	"""A deterministic stroke on a transparent background, like a drawn signature."""
	image = Image.new("RGBA", (300, 100), (0, 0, 0, 0))
	draw = ImageDraw.Draw(image)
	draw.line(
		[(10, 70), (60, 20), (110, 80), (160, 25), (210, 75), (290, 30)], fill=(20, 40, 160, 255), width=6
	)
	out = io.BytesIO()
	image.save(out, "PNG")
	return out.getvalue()


def render(pdf: bytes, page: int = 0) -> Image.Image:
	document = pdfium.PdfDocument(pdf)
	try:
		return document[page].render(scale=SCALE).to_pil().convert("RGB")
	finally:
		document.close()


def colour_bbox(image: Image.Image, colour) -> tuple[int, int, int, int] | None:
	masks = [
		channel.point(lambda v, on=value > 0: 255 if (v > 200 if on else v < 60) else 0)
		for channel, value in zip(image.split(), colour, strict=True)
	]
	mask = masks[0]
	for other in masks[1:]:
		mask = ImageChops.multiply(mask, other)
	return mask.getbbox()


def ink_inside(image: Image.Image, rect: Rect) -> int:
	"""Count of non-white pixels inside a normalized rect."""
	width, height = image.size
	box = (
		int(rect.x * width),
		int(rect.y * height),
		int((rect.x + rect.w) * width),
		int((rect.y + rect.h) * height),
	)
	region = image.crop(box).convert("L")
	return sum(1 for value in region.getdata() if value < 200)


def assert_matches_golden(case: UnitTestCase, image: Image.Image, name: str) -> None:
	path = GOLDEN / f"{name}.png"
	if UPDATE_GOLDEN or not path.exists():
		if not UPDATE_GOLDEN:
			case.fail(f"Golden image {path.name} is missing; run with FRAPPE_SIGN_UPDATE_GOLDEN=1")
		GOLDEN.mkdir(exist_ok=True)
		image.save(path, optimize=True)
		return
	golden = Image.open(path).convert("RGB")
	case.assertEqual(image.size, golden.size, f"{name}: size changed")
	difference = ImageChops.difference(image, golden).convert("L").point(lambda v: 255 if v > 40 else 0)
	changed = sum(1 for value in difference.getdata() if value) / (image.size[0] * image.size[1])
	case.assertLessEqual(changed, GOLDEN_TOLERANCE, f"{name}: {changed:.2%} of pixels differ from golden")


def showcase_fields() -> tuple[list[PlacedField], dict[str, bytes]]:
	fields = [
		PlacedField("signature", "Signature", 1, Rect(0.08, 0.08, 0.35, 0.08)),
		PlacedField("full_name", "Full Name", 1, Rect(0.08, 0.20, 0.4, 0.03), "Ahmed Khan"),
		PlacedField("arabic_name", "Full Name", 1, Rect(0.08, 0.25, 0.4, 0.03), ARABIC_NAME),
		PlacedField("mixed_name", "Text", 1, Rect(0.08, 0.30, 0.4, 0.03), MIXED_NAME),
		PlacedField("date", "Date Signed", 1, Rect(0.55, 0.20, 0.25, 0.03), "2026-11-02"),
		PlacedField("agree", "Checkbox", 1, Rect(0.55, 0.25, 0.03, 0.02), "1"),
		PlacedField("decline", "Checkbox", 1, Rect(0.62, 0.25, 0.03, 0.02), "0"),
		PlacedField(
			"long",
			"Text",
			1,
			Rect(0.08, 0.36, 0.2, 0.02),
			"A very long company name that must shrink to fit its box",
			font_size=14,
		),
		PlacedField("stamp", "Company Stamp", 1, Rect(0.55, 0.32, 0.12, 0.08)),
	]
	captures = {"signature": signature_png(), "stamp": solid_png(80, 80, (200, 30, 30))}
	return fields, captures


class TestText(UnitTestCase):
	def test_arabic_detection_and_direction(self):
		self.assertTrue(has_arabic(ARABIC_NAME))
		self.assertFalse(has_arabic("Ahmed"))
		self.assertTrue(is_rtl(ARABIC_NAME))
		self.assertFalse(is_rtl(MIXED_NAME))

	def test_arabic_is_shaped_and_reordered(self):
		runs = visual_runs(ARABIC_NAME)
		self.assertEqual("".join(text for text, _ in runs), get_display(arabic_reshaper.reshape(ARABIC_NAME)))
		self.assertTrue(all(arabic for text, arabic in runs if text.strip()))
		# Shaping turns the letters into contextual presentation forms.
		self.assertNotEqual("".join(text for text, _ in runs), ARABIC_NAME[::-1])

	def test_mixed_text_splits_into_script_runs(self):
		runs = visual_runs(MIXED_NAME)
		self.assertEqual({arabic for text, arabic in runs if text.strip()}, {True, False})
		self.assertIn(("Ahmed Khan ", False), runs)

	def test_long_text_shrinks_to_fit(self):
		fonts = default_fonts()
		size = fit_font_size(visual_runs("A long value " * 4), fonts, 14, box_width=100, box_height=20)
		self.assertLess(size, 14)
		self.assertGreaterEqual(size, 4)
		self.assertEqual(fit_font_size(visual_runs("Short"), fonts, 11, box_width=300, box_height=20), 11)

	def test_font_size_never_exceeds_the_box_height(self):
		size = fit_font_size(visual_runs("Hi"), default_fonts(), 40, box_width=300, box_height=10)
		self.assertLessEqual(size, 10)


class TestOverlayPositions(UnitTestCase):
	def test_images_land_on_the_coords_json_rects_for_every_fixture(self):
		"""A capture with the rect's aspect ratio fills it; the masked fixture box disappears."""
		for file, fixture_data in COORDS.items():
			metric = fixture_data["pages"][0]
			width, height = metric["display_width"], metric["display_height"]
			fields, captures = [], {}
			for case in fixture_data["cases"]:
				rect = Rect(**case["rect"])
				key = case["name"]
				fields.append(PlacedField(key, "Signature", 1, rect, mask=True))
				captures[key] = solid_png(round(rect.w * width * 4), round(rect.h * height * 4))
			with self.subTest(file=file):
				image = render(apply_fields(fixture(file), fields, captures, default_fonts()))
				for case in fixture_data["cases"]:
					self.assertIsNone(colour_bbox(image, case["color"]), f"{case['name']} box still shows")
				for case in fixture_data["cases"]:
					rect = case["rect"]
					w, h = image.size
					expected = (
						rect["x"] * w,
						rect["y"] * h,
						(rect["x"] + rect["w"]) * w,
						(rect["y"] + rect["h"]) * h,
					)
					# Crop to the case so the three magenta boxes are found one at a time.
					margin = 6
					crop = (
						max(0, int(expected[0]) - margin),
						max(0, int(expected[1]) - margin),
						min(w, int(expected[2]) + margin),
						min(h, int(expected[3]) + margin),
					)
					found = colour_bbox(image.crop(crop), MAGENTA)
					self.assertIsNotNone(found, case["name"])
					found = (found[0] + crop[0], found[1] + crop[1], found[2] + crop[0], found[3] + crop[1])
					for actual, wanted in zip(found, expected, strict=True):
						self.assertLessEqual(
							abs(actual - wanted), 2, f"{file} {case['name']}: {found} vs {expected}"
						)

	def test_text_is_drawn_inside_its_rect_on_rotated_pages(self):
		rect = Rect(0.3, 0.6, 0.4, 0.05)
		field = PlacedField("name", "Full Name", 1, rect, "Ahmed Khan", font_size=14)
		for file in ("rotated_90.pdf", "rotated_270_cropbox.pdf"):
			with self.subTest(file=file):
				image = render(apply_fields(fixture(file), [field], {}, default_fonts()))
				self.assertGreater(ink_inside(image, rect), 50)

	def test_text_reads_upright_on_a_rotated_page(self):
		pdf = apply_fields(
			fixture("rotated_90.pdf"),
			[PlacedField("name", "Text", 1, Rect(0.3, 0.6, 0.4, 0.05), "UPRIGHT")],
			{},
			default_fonts(),
		)
		page = PdfReader(io.BytesIO(pdf)).pages[0]
		# extract_text(orientations=0) keeps only text upright in the page's own space; the value is
		# drawn upright for the reader, so it runs at 90 degrees in user space.
		self.assertIn("UPRIGHT", page.extract_text(orientations=(90,)))
		self.assertNotIn("UPRIGHT", page.extract_text(orientations=(0,)))


class TestOverlayContent(UnitTestCase):
	def test_arabic_name_uses_the_embedded_naskh_font(self):
		rect = Rect(0.1, 0.1, 0.5, 0.05)
		pdf = apply_fields(
			fixture("arabic_text.pdf"),
			[PlacedField("name", "Full Name", 1, rect, ARABIC_NAME, font_size=16)],
			{},
			default_fonts(),
		)
		fonts = PdfReader(io.BytesIO(pdf)).pages[0]["/Resources"]["/Font"]
		base_fonts = {str(font.get_object()["/BaseFont"]) for font in fonts.values()}
		self.assertTrue(any("NotoNaskhArabic" in name for name in base_fonts), base_fonts)
		self.assertGreater(ink_inside(render(pdf), rect), 50)

	def test_showcase_matches_golden(self):
		fields, captures = showcase_fields()
		image = render(apply_fields(fixture("a4_simple.pdf"), fields, captures, default_fonts()))
		assert_matches_golden(self, image, "overlay_showcase_a4")

	def test_rotated_cropbox_matches_golden(self):
		fields, captures = showcase_fields()
		image = render(apply_fields(fixture("rotated_270_cropbox.pdf"), fields, captures, default_fonts()))
		assert_matches_golden(self, image, "overlay_showcase_rotated_270_cropbox")

	def test_unchecked_box_and_missing_values_draw_no_value(self):
		pdf = apply_fields(
			fixture("a4_simple.pdf"),
			[
				PlacedField("empty", "Text", 1, Rect(0.5, 0.6, 0.3, 0.03), ""),
				PlacedField("unsigned", "Signature", 1, Rect(0.5, 0.65, 0.3, 0.05)),
				PlacedField("file", "Attachment", 1, Rect(0.5, 0.7, 0.3, 0.03), "/private/files/x.pdf"),
			],
			{},
			default_fonts(),
		)
		image = render(pdf)
		for rect in (Rect(0.5, 0.6, 0.3, 0.03), Rect(0.5, 0.65, 0.3, 0.05), Rect(0.5, 0.7, 0.3, 0.03)):
			self.assertEqual(ink_inside(image, rect), 0)

	def test_only_pages_with_fields_change(self):
		original = fixture("many_pages_150.pdf")
		pdf = apply_fields(
			original, [PlacedField("n", "Text", 3, Rect(0.1, 0.1, 0.3, 0.03), "Third")], {}, default_fonts()
		)
		before, after = PdfReader(io.BytesIO(original)), PdfReader(io.BytesIO(pdf))
		self.assertEqual(len(after.pages), 150)
		self.assertIn("Third", after.pages[2].extract_text())
		self.assertEqual(after.pages[1].extract_text(), before.pages[1].extract_text())

	def test_overlay_is_deterministic(self):
		fields, captures = showcase_fields()
		pdf = fixture("a4_simple.pdf")
		self.assertEqual(
			apply_fields(pdf, fields, captures, default_fonts()),
			apply_fields(pdf, fields, captures, default_fonts()),
		)

	def test_unreadable_capture_raises(self):
		with self.assertRaises(PdfInvalid):
			apply_fields(
				fixture("a4_simple.pdf"),
				[PlacedField("s", "Signature", 1, Rect(0.1, 0.1, 0.3, 0.05))],
				{"s": b"not an image"},
				default_fonts(),
			)

	def test_field_on_a_missing_page_raises(self):
		with self.assertRaises(PdfInvalid):
			apply_fields(
				fixture("a4_simple.pdf"),
				[PlacedField("s", "Text", 2, Rect(0.1, 0.1, 0.3, 0.05), "x")],
				{},
				default_fonts(),
			)
