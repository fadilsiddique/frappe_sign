"""pdf/seal.py (P1.4): PAdES-B-LT seal that validates with pyHanko, offline."""

import io
from pathlib import Path

from frappe.tests import UnitTestCase
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.timestamps import TimeStamper, TimestampRequestError
from pyhanko.sign.validation import validate_pdf_signature

from frappe_sign.crypto.signer import Pkcs12Signer
from frappe_sign.pdf.seal import SEAL_FIELD, seal_pdf
from frappe_sign.pdf.types import SealError
from frappe_sign.tests import pki

PDFS = Path(__file__).resolve().parents[1] / "fixtures" / "pdfs"


class BrokenTimeStamper(TimeStamper):
	async def async_request_tsa_response(self, req):
		raise TimestampRequestError("every TSA is down")


def seal(pdf: bytes, **overrides) -> bytes:
	options = {
		"signer": pki.sealing_signer(),
		"tsa_urls": ["http://tsa.invalid"],
		"reason": "Signed with Frappe Sign",
		"location": "Dubai",
		"contact": "sign@example.com",
		"timestamper": pki.timestamper(),
		"validation_context": pki.sealing_validation_context(),
		**overrides,
	}
	return seal_pdf(pdf, **options)


class TestSeal(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.original = (PDFS / "a4_simple.pdf").read_bytes()
		cls.sealed = seal(cls.original)

	def test_seal_validates_as_pades_b_lt(self):
		status = pki.validate_lt(self.sealed)
		self.assertTrue(status.bottom_line, status.pretty_print_details())
		self.assertTrue(status.intact and status.valid and status.trusted)
		self.assertTrue(status.timestamp_validity.valid and status.timestamp_validity.trusted)

	def test_seal_carries_revocation_data_and_metadata(self):
		reader = PdfFileReader(io.BytesIO(self.sealed))
		dss = reader.root["/DSS"]
		self.assertGreaterEqual(len(dss["/CRLs"]), 1)
		self.assertGreaterEqual(len(dss["/Certs"]), 2)
		signature = reader.embedded_signatures[0]
		self.assertEqual(signature.field_name, SEAL_FIELD)
		self.assertEqual(signature.sig_object["/SubFilter"], "/ETSI.CAdES.detached")
		self.assertEqual(signature.sig_object["/Reason"], "Signed with Frappe Sign")
		self.assertEqual(signature.sig_object["/Location"], "Dubai")

	def test_original_bytes_are_kept_as_the_first_revision(self):
		self.assertTrue(self.sealed.startswith(self.original))

	def test_tampering_breaks_the_seal(self):
		tampered = self.sealed.replace(b"595.2756", b"595.2757", 1)
		self.assertNotEqual(tampered, self.sealed)
		status = validate_pdf_signature(
			PdfFileReader(io.BytesIO(tampered)).embedded_signatures[0], pki.sealing_validation_context()
		)
		self.assertFalse(status.intact)

	def test_sealing_works_on_rotated_and_arabic_fixtures(self):
		for name in ("rotated_270_cropbox.pdf", "arabic_text.pdf"):
			with self.subTest(name=name):
				status = pki.validate_lt(seal((PDFS / name).read_bytes()))
				self.assertTrue(status.bottom_line, status.pretty_print_details())

	def test_timestamp_failure_raises_seal_error(self):
		with self.assertRaises(SealError):
			seal(self.original, timestamper=BrokenTimeStamper())

	def test_unusable_certificate_raises_seal_error(self):
		bad = Pkcs12Signer((pki.CERTS / "sealing_expired.p12").read_bytes(), pki.P12_PASSWORD)
		with self.assertRaises(SealError):
			seal(self.original, signer=bad)

	def test_a_tsa_url_or_timestamper_is_required(self):
		with self.assertRaises(SealError):
			seal(self.original, tsa_urls=[], timestamper=None)

	def test_garbage_raises_seal_error(self):
		with self.assertRaises(SealError):
			seal(b"not a pdf")
