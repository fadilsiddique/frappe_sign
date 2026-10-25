"""pdf/certificate.py (P1.5): certificate of completion pages, appended before the seal."""

import io
from pathlib import Path

import pypdfium2 as pdfium
from frappe.tests import UnitTestCase
from PIL import Image
from pypdf import PdfReader

from frappe_sign.pdf.certificate import (
	CertificateData,
	CertificateEvent,
	CertificateSigner,
	append_certificate,
	render_certificate,
)
from frappe_sign.pdf.seal import seal_pdf
from frappe_sign.pdf.text import default_fonts
from frappe_sign.tests import pki
from frappe_sign.tests.unit.test_overlay import assert_matches_golden, signature_png

PDFS = Path(__file__).resolve().parents[1] / "fixtures" / "pdfs"
HASH_A = "a" * 64
HASH_B = "b" * 64
HEAD = "c" * 64


def logo_png() -> bytes:
	out = io.BytesIO()
	Image.new("RGB", (120, 40), (15, 118, 110)).save(out, "PNG")
	return out.getvalue()


def sample(events: int = 6, **overrides) -> CertificateData:
	values = {
		"envelope": "SIGN-2026-00001",
		"title": "Quotation SAL-QTN-2026-00042",
		"company": "Upscape Technologies",
		"brand_color": "#0f766e",
		"logo": logo_png(),
		"legal_footer": "Upscape Technologies LLC, Dubai, United Arab Emirates",
		"sender": "Fatima Ali (sales@example.com)",
		"sent_at": "2026-11-01 09:12 GST",
		"completed_at": "2026-11-02 14:31 GST",
		"original_sha256": HASH_A,
		"audit_head": HEAD,
		"verify_url": "https://erp.example.com/sign-verify?envelope=SIGN-2026-00001",
		"signers": [
			CertificateSigner(
				name="Ahmed Khan",
				email="ahmed@example.com",
				role="Customer",
				kind="Signer",
				signed_at="2026-11-02 14:31 GST",
				ip="203.0.113.7",
				intermediate_sha256=HASH_B,
				signature=signature_png(),
			),
			CertificateSigner(
				name="أحمد خان",
				email="ahmed.ar@example.com",
				role="Witness",
				kind="Approver",
				signed_at="2026-11-02 15:02 GST",
				ip="203.0.113.8",
				intermediate_sha256=HASH_B,
			),
		],
		"events": [
			CertificateEvent(
				at=f"2026-11-02 14:{n:02d}:00 UTC",
				event="Viewed",
				actor="ahmed@example.com",
				ip="203.0.113.7",
			)
			for n in range(events)
		],
	}
	values.update(overrides)
	return CertificateData(**values)


def page_text(pdf: bytes) -> str:
	return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


class TestCertificate(UnitTestCase):
	def test_lists_the_envelope_signers_hashes_and_events(self):
		text = page_text(render_certificate(sample(), default_fonts()))
		for expected in (
			"SIGN-2026-00001",
			"Quotation SAL-QTN-2026-00042",
			"Ahmed Khan",
			"ahmed@example.com",
			"203.0.113.7",
			HASH_A,
			HASH_B,
			HEAD,
			"Viewed",
			"Upscape Technologies LLC",
		):
			self.assertIn(expected, text.replace("\n", ""), expected)

	def test_arabic_signer_uses_the_naskh_font(self):
		reader = PdfReader(io.BytesIO(render_certificate(sample(), default_fonts())))
		fonts = {
			str(font.get_object()["/BaseFont"])
			for page in reader.pages
			for font in page["/Resources"]["/Font"].values()
		}
		self.assertTrue(any("NotoNaskhArabic" in name for name in fonts), fonts)

	def test_has_a_qr_code_and_images(self):
		page = PdfReader(io.BytesIO(render_certificate(sample(), default_fonts()))).pages[0]
		# Logo, signature and QR code.
		self.assertGreaterEqual(len(page.images), 3)

	def test_long_event_lists_flow_onto_more_pages(self):
		short = PdfReader(io.BytesIO(render_certificate(sample(events=3), default_fonts())))
		long = PdfReader(io.BytesIO(render_certificate(sample(events=120), default_fonts())))
		self.assertEqual(len(short.pages), 1)
		self.assertGreater(len(long.pages), 2)

	def test_works_without_branding(self):
		pdf = render_certificate(sample(logo=None, brand_color=None, legal_footer=None), default_fonts())
		self.assertIn("SIGN-2026-00001", page_text(pdf))

	def test_bad_brand_colour_falls_back(self):
		pdf = render_certificate(sample(brand_color="not-a-colour"), default_fonts())
		self.assertIn("SIGN-2026-00001", page_text(pdf))

	def test_appended_pages_follow_the_document_and_the_seal_validates(self):
		original = (PDFS / "rotated_90.pdf").read_bytes()
		certificate = render_certificate(sample(), default_fonts())
		combined = append_certificate(original, certificate)
		reader = PdfReader(io.BytesIO(combined))
		self.assertEqual(len(reader.pages), 2)
		self.assertEqual(reader.pages[0].rotation, 90)
		self.assertIn("SIGN-2026-00001", reader.pages[1].extract_text())
		sealed = seal_pdf(
			combined,
			signer=pki.sealing_signer(),
			tsa_urls=[],
			reason="Signed",
			location="",
			contact="",
			timestamper=pki.timestamper(),
			validation_context=pki.sealing_validation_context(),
		)
		status = pki.validate_lt(sealed)
		self.assertTrue(status.bottom_line, status.pretty_print_details())

	def test_rendering_is_deterministic(self):
		self.assertEqual(
			render_certificate(sample(), default_fonts()), render_certificate(sample(), default_fonts())
		)

	def test_first_page_matches_golden(self):
		document = pdfium.PdfDocument(render_certificate(sample(), default_fonts()))
		try:
			image = document[0].render(scale=1.5).to_pil().convert("RGB")
		finally:
			document.close()
		assert_matches_golden(self, image, "certificate_page_1")
