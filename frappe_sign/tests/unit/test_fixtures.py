"""The PDF fixtures are reproducible and exercise what tests/fixtures/README.md says they do."""

import json
import re
import tempfile
from pathlib import Path

from frappe.tests import UnitTestCase
from pypdf import PdfReader

from frappe_sign.tests.fixtures.scripts import check_coords, make_pdfs

FIXTURES_DIR = make_pdfs.FIXTURES_DIR
PDF_DIR = FIXTURES_DIR / "pdfs"
ARABIC = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿]")


def open_pdf(path: Path) -> PdfReader:
	reader = PdfReader(path)
	if reader.is_encrypted:
		reader.decrypt(make_pdfs.ENCRYPTED_USER_PASSWORD)
	return reader


def fingerprint(path: Path) -> tuple:
	"""What a fixture means, independent of library versions: boxes, rotation, text, encryption."""
	reader = open_pdf(path)
	pages = tuple(
		(
			tuple(round(float(v), 3) for v in page.mediabox),
			tuple(round(float(v), 3) for v in page.cropbox),
			page.rotation,
			page.extract_text().strip(),
		)
		for page in reader.pages
	)
	return reader.is_encrypted, pages


class TestFixtures(UnitTestCase):
	def test_coords_match_pdfium(self):
		self.assertEqual(check_coords.check(), [])

	def test_generator_reproduces_the_committed_fixtures(self):
		committed = sorted(path.name for path in PDF_DIR.glob("*.pdf"))
		with tempfile.TemporaryDirectory() as tmp:
			out = Path(tmp)
			make_pdfs.generate(out)
			self.assertEqual(sorted(path.name for path in (out / "pdfs").glob("*.pdf")), committed)
			for name in committed:
				with self.subTest(fixture=name):
					self.assertEqual(fingerprint(out / "pdfs" / name), fingerprint(PDF_DIR / name))
			self.assertEqual(
				json.loads((out / "coords.json").read_text()),
				json.loads((FIXTURES_DIR / "coords.json").read_text()),
			)

	def test_geometry_matches_coords(self):
		coords = json.loads((FIXTURES_DIR / "coords.json").read_text())
		for name, fixture in coords["fixtures"].items():
			page = PdfReader(PDF_DIR / name).pages[0]
			metric = fixture["pages"][0]
			with self.subTest(fixture=name):
				self.assertEqual([round(float(v), 4) for v in page.cropbox], metric["cropbox"])
				self.assertEqual(page.rotation, metric["rotation"])

	def test_encrypted_needs_a_password(self):
		reader = PdfReader(PDF_DIR / "encrypted.pdf")
		self.assertTrue(reader.is_encrypted)
		self.assertTrue(reader.decrypt(make_pdfs.ENCRYPTED_USER_PASSWORD))

	def test_active_content_is_present(self):
		reader = PdfReader(PDF_DIR / "with_javascript.pdf")
		root = reader.trailer["/Root"]
		self.assertIn("/OpenAction", root)
		self.assertIn("/AcroForm", root)
		self.assertIn("/JavaScript", root["/Names"])
		self.assertIn("/EmbeddedFiles", root["/Names"])
		self.assertIn("/AA", reader.pages[0])

	def test_many_pages(self):
		self.assertEqual(len(PdfReader(PDF_DIR / "many_pages_150.pdf").pages), make_pdfs.MANY_PAGES)

	def test_scanned_page_is_only_an_image(self):
		page = PdfReader(PDF_DIR / "scanned_image.pdf").pages[0]
		self.assertEqual(page.extract_text().strip(), "")
		self.assertEqual(len(page.images), 1)

	def test_arabic_text_uses_the_embedded_naskh_font(self):
		page = PdfReader(PDF_DIR / "arabic_text.pdf").pages[0]
		fonts = [font.get_object() for font in page["/Resources"]["/Font"].values()]
		self.assertTrue(any("NotoNaskhArabic" in str(font["/BaseFont"]) for font in fonts))
		self.assertRegex(page.extract_text(), ARABIC)
