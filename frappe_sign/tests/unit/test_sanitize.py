"""pdf/sanitize.py (P1.2): reject encrypted PDFs, enforce caps, strip active content."""

import io
from pathlib import Path

from frappe.tests import UnitTestCase
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
	ArrayObject,
	DictionaryObject,
	FloatObject,
	IndirectObject,
	NameObject,
	TextStringObject,
)

from frappe_sign.pdf.pages import page_metrics
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.types import PdfEncrypted, PdfInvalid, PdfTooLarge, PdfTooManyPages
from frappe_sign.utils.hashing import sha256_hex

PDFS = Path(__file__).resolve().parents[1] / "fixtures" / "pdfs"
BIG = 50 * 1024 * 1024
FORBIDDEN_KEYS = {"/JavaScript", "/JS", "/OpenAction", "/AA", "/EmbeddedFiles", "/AcroForm", "/Launch"}


def fixture(name: str) -> bytes:
	return (PDFS / name).read_bytes()


def all_keys_and_names(pdf: bytes) -> set[str]:
	"""Every dictionary key and name value reachable from the trailer."""
	reader = PdfReader(io.BytesIO(pdf))
	found: set[str] = set()
	seen: set[int] = set()
	stack = [reader.trailer]
	while stack:
		obj = stack.pop()
		if isinstance(obj, IndirectObject):
			if obj.idnum in seen:
				continue
			seen.add(obj.idnum)
			obj = obj.get_object()
		if isinstance(obj, DictionaryObject):
			for key, value in obj.items():
				found.add(str(key))
				stack.append(value)
		elif isinstance(obj, ArrayObject):
			stack.extend(obj)
		elif isinstance(obj, NameObject):
			found.add(str(obj))
	return found


def with_link_annotations(pdf: bytes) -> bytes:
	"""Add a JavaScript link and a plain URI link to the first page."""
	writer = PdfWriter(clone_from=PdfReader(io.BytesIO(pdf)))
	rect = ArrayObject([FloatObject(v) for v in (72, 72, 200, 100)])

	def link(action: dict) -> DictionaryObject:
		annotation = DictionaryObject(
			{
				NameObject("/Type"): NameObject("/Annot"),
				NameObject("/Subtype"): NameObject("/Link"),
				NameObject("/Rect"): rect,
				NameObject("/A"): DictionaryObject(action),
			}
		)
		return writer._add_object(annotation)

	page = writer.pages[0]
	page[NameObject("/Annots")] = ArrayObject(
		[
			link({NameObject("/S"): NameObject("/JavaScript"), NameObject("/JS"): TextStringObject("x()")}),
			link({NameObject("/S"): NameObject("/URI"), NameObject("/URI"): TextStringObject("https://a.b")}),
		]
	)
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


class TestSanitize(UnitTestCase):
	def test_encrypted_pdf_is_rejected(self):
		with self.assertRaises(PdfEncrypted):
			sanitize(fixture("encrypted.pdf"), max_bytes=BIG, max_pages=200)

	def test_garbage_is_rejected(self):
		with self.assertRaises(PdfInvalid):
			sanitize(b"%PDF-1.7 nothing here", max_bytes=BIG, max_pages=200)

	def test_size_cap(self):
		data = fixture("a4_simple.pdf")
		with self.assertRaises(PdfTooLarge):
			sanitize(data, max_bytes=len(data) - 1, max_pages=200)
		sanitize(data, max_bytes=len(data), max_pages=200)

	def test_page_cap(self):
		with self.assertRaises(PdfTooManyPages):
			sanitize(fixture("many_pages_150.pdf"), max_bytes=BIG, max_pages=149)
		self.assertEqual(
			sanitize(fixture("many_pages_150.pdf"), max_bytes=BIG, max_pages=150).page_count, 150
		)

	def test_active_content_is_stripped(self):
		original = fixture("with_javascript.pdf")
		self.assertTrue(FORBIDDEN_KEYS & all_keys_and_names(original), "fixture lost its active content")
		result = sanitize(original, max_bytes=BIG, max_pages=200)
		self.assertEqual(FORBIDDEN_KEYS & all_keys_and_names(result.data), set())
		page = PdfReader(io.BytesIO(result.data)).pages[0]
		self.assertNotIn("/Annots", page, "the AcroForm widget must go with the form")
		self.assertIn("frappe_sign fixture", page.extract_text())

	def test_javascript_links_go_and_plain_links_stay(self):
		result = sanitize(with_link_annotations(fixture("a4_simple.pdf")), max_bytes=BIG, max_pages=200)
		annotations = [a.get_object() for a in PdfReader(io.BytesIO(result.data)).pages[0]["/Annots"]]
		self.assertEqual([a["/A"]["/S"] for a in annotations], ["/URI"])
		self.assertNotIn("/JavaScript", all_keys_and_names(result.data))

	def test_geometry_text_and_hash_are_kept(self):
		for name in ("rotated_90.pdf", "offset_cropbox.pdf", "rotated_270_cropbox.pdf", "arabic_text.pdf"):
			with self.subTest(name=name):
				original = fixture(name)
				result = sanitize(original, max_bytes=BIG, max_pages=200)
				self.assertEqual(result.metrics, page_metrics(original))
				self.assertEqual(page_metrics(result.data), page_metrics(original))
				self.assertEqual(result.sha256, sha256_hex(result.data))
				before = PdfReader(io.BytesIO(original)).pages[0].extract_text()
				after = PdfReader(io.BytesIO(result.data)).pages[0].extract_text()
				self.assertEqual(after, before)

	def test_output_is_stable(self):
		"""The same input gives the same bytes, so the frozen hash is reproducible."""
		data = fixture("with_javascript.pdf")
		first = sanitize(data, max_bytes=BIG, max_pages=200)
		self.assertEqual(sanitize(data, max_bytes=BIG, max_pages=200).sha256, first.sha256)
