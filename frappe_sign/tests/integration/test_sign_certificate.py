"""Sign Certificate parses and checks its PKCS#12 file on save (DESIGN 2.1)."""

from datetime import datetime

import frappe
from frappe.tests import IntegrationTestCase

from frappe_sign.exceptions import CertificateError
from frappe_sign.tests.factories import make_certificate


class TestSignCertificate(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_valid_certificate_fills_its_details(self):
		certificate = make_certificate()
		self.assertIn("Frappe Sign Test Seal", certificate.subject)
		self.assertIn("Frappe Sign Test Root CA", certificate.issuer)
		self.assertEqual(certificate.valid_to, datetime(2041, 1, 1))
		self.assertRegex(certificate.fingerprint_sha256, r"^[0-9a-f]{64}$")
		self.assertEqual(certificate.get_password("p12_password"), "fixture-seal")

	def test_details_are_parsed_again_when_saved_with_the_stored_password(self):
		certificate = make_certificate()
		certificate.reload()
		certificate.subject = "edited"
		certificate.save()
		self.assertIn("Frappe Sign Test Seal", certificate.subject)

	def test_unusable_files_are_rejected(self):
		for p12_name, password in (
			("sealing.p12", "wrong"),
			("sealing_expired.p12", "fixture-seal"),
			("sealing_no_key.p12", "fixture-seal"),
		):
			with self.subTest(p12=p12_name):
				self.assertRaises(CertificateError, make_certificate, p12_name, password)

	def test_file_and_password_are_required(self):
		self.assertRaises(CertificateError, make_certificate, p12_file=None)
		self.assertRaises(CertificateError, make_certificate, password="")
