"""services/certificates.py: "Create test certificate" gives a site a working seal in one step."""

import frappe
from frappe.tests import IntegrationTestCase

from frappe_sign.crypto import pkcs12
from frappe_sign.exceptions import CertificateError
from frappe_sign.services import sealing
from frappe_sign.services.certificates import create_test_certificate
from frappe_sign.tests.factories import make_certificate, make_user, test_company


class TestCreateTestCertificate(IntegrationTestCase):
	def setUp(self):
		self.company = test_company()
		# Start from a site without profiles; the rollback in tearDown puts them back.
		frappe.db.delete("Sign Profile")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_creates_the_certificate_its_private_file_and_the_profile(self):
		result = create_test_certificate(self.company)
		certificate = frappe.get_doc("Sign Certificate", result["certificate"])
		self.assertEqual(certificate.kind, "Self-signed")
		self.assertEqual(certificate.company, self.company)
		self.assertIn(f"CN={self.company}", certificate.subject)
		self.assertEqual(certificate.subject, certificate.issuer)

		file = frappe.get_doc("File", {"file_url": certificate.p12_file})
		self.assertEqual(file.is_private, 1)
		self.assertEqual(
			(file.attached_to_doctype, file.attached_to_name), ("Sign Certificate", certificate.name)
		)
		password = certificate.get_password("p12_password")
		self.assertTrue(pkcs12.inspect(file.get_content(encodings=[]), password.encode()).has_key)

		self.assertEqual(result["profile_action"], "created")
		self.assertEqual(
			frappe.db.get_value("Sign Profile", self.company, "sealing_certificate"), certificate.name
		)

	def test_the_seal_job_can_use_it(self):
		create_test_certificate(self.company)
		signer = sealing.sealing_signer(self.company).pyhanko_signer()
		self.assertIn(self.company, signer.signing_cert.subject.human_friendly)

	def test_links_a_profile_without_a_certificate(self):
		frappe.get_doc({"doctype": "Sign Profile", "company": self.company}).insert()
		result = create_test_certificate(self.company, common_name="Pilot Seal", years=1)
		self.assertEqual(result["profile_action"], "linked")
		self.assertEqual(
			frappe.db.get_value("Sign Profile", self.company, "sealing_certificate"), result["certificate"]
		)
		self.assertIn(
			"CN=Pilot Seal", frappe.db.get_value("Sign Certificate", result["certificate"], "subject")
		)

	def test_never_replaces_a_profile_certificate(self):
		existing = make_certificate().name
		frappe.get_doc(
			{"doctype": "Sign Profile", "company": self.company, "sealing_certificate": existing}
		).insert()
		result = create_test_certificate(self.company)
		self.assertIsNone(result["profile_action"])
		self.assertEqual(frappe.db.get_value("Sign Profile", self.company, "sealing_certificate"), existing)

	def test_without_a_company_no_profile_is_made(self):
		result = create_test_certificate(common_name="Trial Seal")
		self.assertIsNone(result["profile"])
		self.assertFalse(frappe.db.count("Sign Profile"))

	def test_a_name_and_a_sensible_validity_are_required(self):
		self.assertRaises(CertificateError, create_test_certificate)
		self.assertRaises(CertificateError, create_test_certificate, self.company, years=0)
		self.assertRaises(CertificateError, create_test_certificate, self.company, years=11)

	def test_only_a_system_manager_can_create_one(self):
		make_user("cert-manager@example.com", "Sign Manager")
		frappe.set_user("cert-manager@example.com")
		self.assertRaises(frappe.PermissionError, create_test_certificate, self.company)
