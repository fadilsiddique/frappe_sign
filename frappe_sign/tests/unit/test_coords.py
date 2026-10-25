"""Coordinate conversion against tests/fixtures/coords.json (P1.1, D7).

The expected values come from check_coords.py, which confirms them with pdfium, not from the code
under test. frontend/tests/coords.test.ts checks shared/coords.ts against the same file.
"""

import json
from pathlib import Path

from frappe.tests import UnitTestCase

from frappe_sign.pdf.pages import page_metrics
from frappe_sign.pdf.types import (
	Box,
	PageMetric,
	PdfInvalid,
	Rect,
	display_matrix,
	display_to_user,
	normalized_to_pdf,
	pdf_to_normalized,
	user_to_display,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
COORDS = json.loads((FIXTURES / "coords.json").read_text())["fixtures"]
PLACES = 3


def metric_from_fixture(page: dict) -> PageMetric:
	x0, y0, x1, y1 = page["cropbox"]
	return PageMetric(
		page=page["page"], width=x1 - x0, height=y1 - y0, rotation=page["rotation"], left=x0, bottom=y0
	)


class TestPageMetrics(UnitTestCase):
	def test_metrics_read_from_every_fixture_match_coords_json(self):
		for file, fixture in COORDS.items():
			with self.subTest(file=file):
				metrics = page_metrics((FIXTURES / "pdfs" / file).read_bytes())
				for expected in fixture["pages"]:
					metric = metrics[expected["page"] - 1]
					self.assertEqual(metric, metric_from_fixture(expected))
					self.assertAlmostEqual(metric.display_width, expected["display_width"], PLACES)
					self.assertAlmostEqual(metric.display_height, expected["display_height"], PLACES)

	def test_metrics_round_trip_through_json(self):
		metric = PageMetric(page=2, width=480, height=720, rotation=270, left=40, bottom=60)
		self.assertEqual(PageMetric.from_dict(json.loads(json.dumps(metric.to_dict()))), metric)

	def test_page_metrics_rejects_garbage(self):
		with self.assertRaises(PdfInvalid):
			page_metrics(b"not a pdf")

	def test_rotation_is_normalized_and_checked(self):
		self.assertEqual(PageMetric(page=1, width=10, height=20, rotation=-90).rotation, 270)
		self.assertEqual(PageMetric(page=1, width=10, height=20, rotation=450).rotation, 90)
		with self.assertRaises(PdfInvalid):
			PageMetric(page=1, width=10, height=20, rotation=45)


class TestConversion(UnitTestCase):
	def assert_box(self, box: Box, expected: list[float]):
		for actual, wanted in zip(box.as_list(), expected, strict=True):
			self.assertAlmostEqual(actual, wanted, PLACES)

	def assert_rect(self, rect: Rect, expected: dict):
		for key in "xywh":
			self.assertAlmostEqual(getattr(rect, key), expected[key], PLACES)

	def each_case(self):
		for file, fixture in COORDS.items():
			metrics = {page["page"]: metric_from_fixture(page) for page in fixture["pages"]}
			for case in fixture["cases"]:
				yield file, metrics[case["page"]], case

	def test_normalized_to_pdf_matches_every_case(self):
		for file, metric, case in self.each_case():
			with self.subTest(file=file, case=case["name"]):
				self.assert_box(normalized_to_pdf(metric, Rect(**case["rect"])), case["pdf_rect"])

	def test_pdf_to_normalized_is_the_inverse(self):
		for file, metric, case in self.each_case():
			with self.subTest(file=file, case=case["name"]):
				self.assert_rect(pdf_to_normalized(metric, Box(*case["pdf_rect"])), case["rect"])

	def test_display_points_round_trip(self):
		for file, metric, _case in self.each_case():
			with self.subTest(file=file):
				for x, y in ((0, 0), (12.5, 30), (metric.display_width, metric.display_height)):
					ux, uy = display_to_user(metric, x, y)
					dx, dy = user_to_display(metric, ux, uy)
					self.assertAlmostEqual(dx, x, PLACES)
					self.assertAlmostEqual(dy, y, PLACES)

	def test_display_matrix_maps_bottom_left_display_space_to_user_space(self):
		"""The overlay draws upright in display space; the matrix must land on the same user rect."""
		for file, metric, case in self.each_case():
			with self.subTest(file=file, case=case["name"]):
				a, b, c, d, e, f = display_matrix(metric)
				rect = Rect(**case["rect"])
				# Display space for drawing: origin at the bottom-left of the shown page, y up.
				u0 = rect.x * metric.display_width
				v0 = (1 - rect.y - rect.h) * metric.display_height
				u1 = (rect.x + rect.w) * metric.display_width
				v1 = (1 - rect.y) * metric.display_height
				points = [(a * u + c * v + e, b * u + d * v + f) for u in (u0, u1) for v in (v0, v1)]
				xs, ys = [p[0] for p in points], [p[1] for p in points]
				self.assert_box(Box(min(xs), min(ys), max(xs), max(ys)), case["pdf_rect"])

	def test_rotation_180_is_supported(self):
		metric = PageMetric(page=1, width=200, height=100, rotation=180, left=10, bottom=20)
		box = normalized_to_pdf(metric, Rect(0, 0, 0.5, 0.5))
		# The shown top-left corner is the user space top-right of the CropBox.
		self.assert_box(box, [110, 20, 210, 70])
		self.assert_rect(pdf_to_normalized(metric, box), {"x": 0, "y": 0, "w": 0.5, "h": 0.5})
