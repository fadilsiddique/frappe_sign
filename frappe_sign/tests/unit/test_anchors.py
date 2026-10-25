"""pdf/anchors.py: find [[fs:...]] markers and turn them into normalized rects (DESIGN 4.2, P2.2).

The PDFs here are drawn with reportlab, with markers at known places. Real Print Formats rendered
with wkhtmltopdf and chrome are tested in tests/erpnext/test_anchors_quotation.py.
"""

import io

import frappe
from frappe.tests import UnitTestCase
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas

from frappe_sign.jinja import sign_field
from frappe_sign.pdf.anchors import MM, find_anchors, marker, role_token
from frappe_sign.pdf.source import anchor_registry, start_anchor_registry
from frappe_sign.pdf.types import PdfInvalid

A4 = (595.0, 842.0)
PLACES = 3


def marker_pdf(markers: list[tuple[str, float, float]], pagesize=A4, font_size=1.0, pages=1, rotate=0):
	"""One or more pages with each marker's top-left at (x, y) points from the page's top-left."""
	buffer = io.BytesIO()
	pdf = canvas.Canvas(buffer, pagesize=pagesize)
	for page in range(1, pages + 1):
		pdf.setFont("Helvetica", 12)
		pdf.drawString(72, pagesize[1] - 72, f"Page {page}")
		pdf.setFont("Helvetica", font_size)
		pdf.setFillColorRGB(1, 1, 1)
		for text, x, y in markers if page == pages else []:
			pdf.drawString(x, pagesize[1] - y - 0.8 * font_size, text)
		pdf.setFillColorRGB(0, 0, 0)
		pdf.showPage()
	pdf.save()
	if not rotate:
		return buffer.getvalue()
	writer = PdfWriter(clone_from=PdfReader(io.BytesIO(buffer.getvalue())))
	for page in writer.pages:
		page.rotate(rotate)
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


class TestMarkers(UnitTestCase):
	def test_marker_format(self):
		self.assertEqual(marker("Customer", "signature", 1), "[[fs:Customer:signature:1]]")
		self.assertEqual(marker("Sales Manager", "Date Signed", 2), "[[fs:Sales_Manager:date_signed:2]]")

	def test_role_and_type_must_be_markable(self):
		for role in ("", "عميل", "a:b"):
			with self.subTest(role=role), self.assertRaises(ValueError):
				role_token(role)
		with self.assertRaises(ValueError):
			marker("Customer", "attachment", 1)


class TestFindAnchors(UnitTestCase):
	def test_rect_from_the_marker_and_the_declared_size(self):
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 100, 200)])
		[anchor] = find_anchors(pdf, {"[[fs:Customer:signature:1]]": (60.0, 20.0)})
		self.assertEqual(
			(anchor.role, anchor.field_type, anchor.n, anchor.page), ("Customer", "Signature", 1, 1)
		)
		self.assertAlmostEqual(anchor.rect.x, 100 / A4[0], PLACES)
		self.assertAlmostEqual(anchor.rect.y, 200 / A4[1], PLACES)
		self.assertAlmostEqual(anchor.rect.w, 60 * MM / A4[0], PLACES)
		self.assertAlmostEqual(anchor.rect.h, 20 * MM / A4[1], PLACES)

	def test_default_size_per_field_type(self):
		pdf = marker_pdf([("[[fs:Company:company_stamp:1]]", 50, 50)])
		[anchor] = find_anchors(pdf)
		self.assertAlmostEqual(anchor.rect.w, 40 * MM / A4[0], PLACES)
		self.assertAlmostEqual(anchor.rect.h, 40 * MM / A4[1], PLACES)

	def test_markers_side_by_side_get_their_own_positions(self):
		pdf = marker_pdf(
			[("[[fs:Customer:signature:1]]", 100, 300), ("[[fs:Customer:date_signed:1]]", 300, 300)]
		)
		anchors = {anchor.field_type: anchor for anchor in find_anchors(pdf)}
		self.assertAlmostEqual(anchors["Signature"].rect.x, 100 / A4[0], PLACES)
		self.assertAlmostEqual(anchors["Date Signed"].rect.x, 300 / A4[0], PLACES)

	def test_scaled_marker_scales_the_rect(self):
		# A generator that zooms content to 75% draws the 1pt marker at 0.75pt.
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 100, 200)], font_size=0.75)
		[anchor] = find_anchors(pdf, {"[[fs:Customer:signature:1]]": (60.0, 20.0)})
		self.assertAlmostEqual(anchor.rect.w, 0.75 * 60 * MM / A4[0], PLACES)

	def test_resized_marker_keeps_the_declared_size(self):
		# A minimum font size drew the marker at 9pt; that is not a zoom of the content.
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 100, 200)], font_size=9)
		[anchor] = find_anchors(pdf, {"[[fs:Customer:signature:1]]": (60.0, 20.0)})
		self.assertAlmostEqual(anchor.rect.w, 60 * MM / A4[0], PLACES)

	def test_marker_on_a_later_page(self):
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 100, 200)], pages=3)
		[anchor] = find_anchors(pdf)
		self.assertEqual(anchor.page, 3)

	def test_rotated_page_uses_the_visible_box(self):
		# The marker sits at user space (100, 200 from the top); /Rotate 90 shows that point at
		# display (842 - 200 - ..., 100) on a landscape page.
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 100, 200)], rotate=90)
		[anchor] = find_anchors(pdf)
		self.assertAlmostEqual(anchor.rect.y, 100 / A4[0], 2)
		self.assertGreater(anchor.rect.x, 0.5)

	def test_rect_stays_on_the_page(self):
		pdf = marker_pdf([("[[fs:Customer:signature:1]]", 560, 830)])
		[anchor] = find_anchors(pdf, {"[[fs:Customer:signature:1]]": (60.0, 20.0)})
		self.assertLessEqual(anchor.rect.x + anchor.rect.w, 1 + 1e-9)
		self.assertLessEqual(anchor.rect.y + anchor.rect.h, 1 + 1e-9)

	def test_first_occurrence_wins_and_unknown_types_are_ignored(self):
		pdf = marker_pdf(
			[
				("[[fs:Customer:signature:1]]", 100, 200),
				("[[fs:Customer:signature:1]]", 100, 600),
				("[[fs:Customer:hologram:1]]", 100, 400),
			]
		)
		anchors = find_anchors(pdf)
		self.assertEqual([anchor.tag for anchor in anchors], ["[[fs:Customer:signature:1]]"])
		self.assertAlmostEqual(anchors[0].rect.y, 200 / A4[1], PLACES)

	def test_pdf_without_markers(self):
		self.assertEqual(find_anchors(marker_pdf([])), [])

	def test_unreadable_pdf(self):
		with self.assertRaises(PdfInvalid):
			find_anchors(b"%PDF-1.4 not really")


class TestSignField(UnitTestCase):
	def setUp(self):
		super().setUp()
		start_anchor_registry()

	def test_markup_has_the_marker_and_the_size(self):
		html = str(sign_field("signature", role="Customer", width=60, height=20, border=True))
		self.assertIn("[[fs:Customer:signature:1]]", html)
		self.assertIn("width:60.0mm;height:20.0mm", html)
		self.assertIn("dotted", html)
		self.assertIn("font-size:1pt", html)
		self.assertEqual(anchor_registry()["sizes"], {"[[fs:Customer:signature:1]]": (60.0, 20.0)})

	def test_n_counts_calls_per_role_and_type(self):
		sign_field("signature", role="Customer")
		second = str(sign_field("signature", role="Customer"))
		other = str(sign_field("signature", role="Company"))
		explicit = str(sign_field("initials", role="Customer", n=5))
		self.assertIn("[[fs:Customer:signature:2]]", second)
		self.assertIn("[[fs:Company:signature:1]]", other)
		self.assertIn("[[fs:Customer:initials:5]]", explicit)

	def test_default_size_and_no_border(self):
		html = str(sign_field("Date Signed", role="Sales Manager"))
		self.assertIn("[[fs:Sales_Manager:date_signed:1]]", html)
		self.assertIn("width:40.0mm;height:8.0mm", html)
		self.assertNotIn("dotted", html)

	def test_bad_arguments_stop_the_print(self):
		for kwargs in (
			{"field_type": "hologram", "role": "Customer"},
			{"field_type": "signature", "role": "a:b"},
			{"field_type": "signature", "role": "Customer", "width": 0},
			{"field_type": "signature", "role": "Customer", "height": 1000},
		):
			with self.subTest(**kwargs), self.assertRaises(frappe.ValidationError):
				sign_field(**kwargs)
