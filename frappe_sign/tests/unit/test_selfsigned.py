"""crypto/selfsigned.py: a self-signed sealing certificate that the controller accepts and that seals."""

import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12 as crypto_pkcs12
from frappe.tests import UnitTestCase
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from frappe_sign.crypto import pkcs12
from frappe_sign.crypto.selfsigned import CLOCK_SKEW, make_self_signed
from frappe_sign.crypto.signer import Pkcs12Signer
from frappe_sign.pdf.seal import seal_pdf
from frappe_sign.tests import pki

PDFS = Path(__file__).resolve().parents[1] / "fixtures" / "pdfs"


class TestSelfSigned(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.material = make_self_signed("Acme Trading LLC", organization="Acme Trading LLC")

	def info(self, material=None) -> pkcs12.Pkcs12Info:
		material = material or self.material
		return pkcs12.inspect(material.p12, material.password.encode())

	def test_opens_with_its_password_and_is_usable_now(self):
		info = self.info()
		pkcs12.require_usable(info, now=datetime.now(UTC).replace(tzinfo=None))
		self.assertTrue(info.has_key)
		self.assertIn("CN=Acme Trading LLC", info.subject)
		self.assertIn("O=Acme Trading LLC", info.subject)
		self.assertEqual(info.subject, info.issuer)

	def test_validity_follows_the_years(self):
		now = datetime(2026, 10, 25, tzinfo=UTC)
		info = self.info(make_self_signed("Acme", years=2, now=now))
		self.assertEqual(info.valid_from, (now - CLOCK_SKEW).replace(tzinfo=None))
		self.assertEqual(info.valid_to, (now + timedelta(days=730)).replace(tzinfo=None))
		self.assertEqual(info.subject, "CN=Acme")

	def test_a_wrong_password_does_not_open_it(self):
		with self.assertRaises(pkcs12.Pkcs12Error):
			pkcs12.inspect(self.material.p12, b"wrong")

	def test_each_call_makes_a_new_key_and_password(self):
		other = make_self_signed("Acme Trading LLC")
		self.assertNotEqual(other.password, self.material.password)
		self.assertNotEqual(self.info(other).fingerprint_sha256, self.info().fingerprint_sha256)

	def test_key_usage_allows_signing_only(self):
		_key, certificate, _extra = crypto_pkcs12.load_key_and_certificates(
			self.material.p12, self.material.password.encode()
		)
		usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
		self.assertTrue(usage.digital_signature and usage.content_commitment)
		self.assertFalse(usage.key_cert_sign)
		self.assertFalse(certificate.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)

	def test_bad_input_is_refused(self):
		for kwargs in (
			{"common_name": " "},
			{"common_name": "Acme", "years": 0},
			{"common_name": "Acme", "years": 11},
		):
			with self.subTest(**kwargs), self.assertRaises(ValueError):
				make_self_signed(**kwargs)

	def test_repr_hides_the_key_material(self):
		self.assertNotIn(self.material.password, repr(self.material))

	def test_it_seals_a_pdf_that_validates_against_itself(self):
		signer = Pkcs12Signer(self.material.p12, self.material.password.encode())
		leaf = signer.pyhanko_signer().signing_cert
		sealed = seal_pdf(
			(PDFS / "a4_simple.pdf").read_bytes(),
			signer=signer,
			tsa_urls=["http://tsa.invalid"],
			reason="Signed with Frappe Sign",
			location="Dubai",
			contact="sign@example.com",
			timestamper=pki.timestamper(),
			validation_context=ValidationContext(
				trust_roots=[leaf, pki.root_cert()],
				crls=[pki.root_crl()],
				allow_fetching=False,
				revocation_mode="soft-fail",
			),
		)
		signature = PdfFileReader(io.BytesIO(sealed)).embedded_signatures[0]
		status = validate_pdf_signature(
			signature,
			# The root is only there for the test TSA's timestamp; the seal itself chains to `leaf`.
			signer_validation_context=ValidationContext(
				trust_roots=[leaf, pki.root_cert()], allow_fetching=False, revocation_mode="soft-fail"
			),
		)
		self.assertTrue(status.intact and status.valid and status.trusted, status.pretty_print_details())
