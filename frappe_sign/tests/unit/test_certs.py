"""The test PKI in tests/fixtures/certs/ is usable for sealing (P0.8)."""

import io
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID
from frappe.tests import UnitTestCase
from pyhanko.keys import load_cert_from_pemder
from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign import signers
from pyhanko.sign.validation import validate_pdf_signature
from pyhanko_certvalidator import ValidationContext

from frappe_sign.tests.fixtures.scripts import make_certs, make_pdfs

CERTS = make_certs.CERTS_DIR
PASSWORD = make_certs.P12_PASSWORD


def load_p12(name: str, password: bytes = PASSWORD):
	return pkcs12.load_key_and_certificates((CERTS / name).read_bytes(), password)


def describe(certs_dir: Path) -> dict:
	"""Everything but the random keys: names, serials, dates and extensions of each certificate."""

	def summary(cert: x509.Certificate) -> tuple:
		extensions = sorted((ext.oid.dotted_string, ext.critical) for ext in cert.extensions)
		return (
			cert.subject,
			cert.issuer,
			cert.serial_number,
			cert.not_valid_before_utc,
			cert.not_valid_after_utc,
			extensions,
		)

	described = {}
	for path in sorted(certs_dir.iterdir()):
		data = path.read_bytes()
		if path.suffix == ".p12":
			key, cert, chain = pkcs12.load_key_and_certificates(data, PASSWORD)
			described[path.name] = (key is not None, [summary(c) for c in [cert, *chain] if c])
		elif path.name.endswith(".key.pem"):
			described[path.name] = b"PRIVATE KEY" in data
		elif path.suffix == ".pem":
			described[path.name] = summary(x509.load_pem_x509_certificate(data))
		elif path.suffix == ".crl":
			crl = x509.load_der_x509_crl(data)
			described[path.name] = (crl.issuer, crl.last_update_utc, crl.next_update_utc, len(list(crl)))
	return described


def root_ca() -> x509.Certificate:
	return x509.load_pem_x509_certificate((CERTS / "root_ca.pem").read_bytes())


class TestCertificates(UnitTestCase):
	def test_script_reproduces_the_committed_pki(self):
		committed = {path.name for path in CERTS.iterdir() if path.name != "README.md"}
		with tempfile.TemporaryDirectory() as tmp:
			make_certs.generate(Path(tmp))
			self.assertEqual({path.name for path in Path(tmp).iterdir()}, committed)
			expected = {k: v for k, v in describe(CERTS).items() if k in committed}
			self.assertEqual(describe(Path(tmp)), expected)

	def test_sealing_p12_chains_to_the_root(self):
		key, cert, chain = load_p12("sealing.p12")
		self.assertIsNotNone(key)
		cert.verify_directly_issued_by(root_ca())
		self.assertEqual([c.subject for c in chain], [root_ca().subject])
		self.assertLess(datetime.now(UTC), cert.not_valid_after_utc)

	def test_wrong_password_is_rejected(self):
		with self.assertRaises(ValueError):
			load_p12("sealing.p12", b"wrong")

	def test_expired_and_key_less_variants(self):
		_, expired, _ = load_p12("sealing_expired.p12")
		self.assertLess(expired.not_valid_after_utc, datetime.now(UTC))
		# Without a key, the leaf is stored as one more certificate rather than the main one.
		key, cert, chain = load_p12("sealing_no_key.p12")
		self.assertIsNone(key)
		subjects = [c.subject.rfc4514_string() for c in [cert, *chain] if c]
		self.assertTrue(any("CN=Frappe Sign Test Seal" in subject for subject in subjects), subjects)

	def test_seal_certificate_may_sign_documents(self):
		_, cert, _ = load_p12("sealing.p12")
		usage = cert.extensions.get_extension_for_class(x509.KeyUsage).value
		self.assertTrue(usage.digital_signature and usage.content_commitment)
		self.assertFalse(cert.extensions.get_extension_for_class(x509.BasicConstraints).value.ca)

	def test_tsa_certificate_is_for_timestamping_only(self):
		tsa = x509.load_pem_x509_certificate((CERTS / "tsa.pem").read_bytes())
		extension = tsa.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
		self.assertTrue(extension.critical)
		self.assertEqual(list(extension.value), [ExtendedKeyUsageOID.TIME_STAMPING])
		tsa.verify_directly_issued_by(root_ca())

	def test_crl_is_signed_by_the_root(self):
		crl = x509.load_der_x509_crl((CERTS / "root_ca.crl").read_bytes())
		self.assertTrue(crl.is_signature_valid(root_ca().public_key()))
		self.assertEqual(len(list(crl)), 0)

	def test_pyhanko_seals_and_validates_with_the_test_pki(self):
		"""Sign a fixture PDF with sealing.p12 and validate it against the root and its CRL, offline."""
		signer = signers.SimpleSigner.load_pkcs12(pfx_file=str(CERTS / "sealing.p12"), passphrase=PASSWORD)
		self.assertIsNotNone(signer)
		pdf = (make_pdfs.FIXTURES_DIR / "pdfs" / "a4_simple.pdf").read_bytes()
		writer = IncrementalPdfFileWriter(io.BytesIO(pdf))
		sealed = signers.sign_pdf(writer, signers.PdfSignatureMetadata(field_name="Seal"), signer=signer)

		context = ValidationContext(
			trust_roots=[load_cert_from_pemder(str(CERTS / "root_ca.pem"))],
			crls=[(CERTS / "root_ca.crl").read_bytes()],
			allow_fetching=False,
			revocation_mode="hard-fail",
		)
		signature = PdfFileReader(sealed).embedded_signatures[0]
		status = validate_pdf_signature(signature, context)
		self.assertTrue(status.bottom_line, status.pretty_print_details())
