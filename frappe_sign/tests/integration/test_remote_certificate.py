"""Remote Sign Certificates (P3.6): config checks, the signer the seal job gets, and reading the
certificate from the token."""

import json

import frappe

from frappe_sign.crypto.remote import RemoteSigner
from frappe_sign.exceptions import CertificateError
from frappe_sign.services import certificates, schedule, sealing
from frappe_sign.tests import softhsm
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_profile, make_user, test_company


class RemoteCase(SignTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.token = softhsm.require()

	def config(self, **overrides) -> dict:
		return {
			"type": "pkcs11",
			"module_path": self.token.module_path,
			"token_label": self.token.token_label,
			"key_label": self.token.key_label,
		} | overrides

	def certificate(self, config: dict | None = None, pin: str | None = None):
		return frappe.get_doc(
			{
				"doctype": "Sign Certificate",
				"title": "HSM Seal",
				"kind": "CA-issued",
				"storage": "Remote",
				"remote_config": json.dumps(config or self.config()),
				"remote_pin": self.token.pin if pin is None else pin,
			}
		).insert()


class TestSave(RemoteCase):
	def test_a_valid_config_saves_without_a_p12_file(self):
		self.assertEqual(self.certificate().storage, "Remote")

	def test_a_bad_config_is_refused_with_a_reason(self):
		for config, text in (
			(self.config(module_path="relative.so"), "absolute path"),
			(self.config(token_label=None, slot_no=None), "token_label"),
			(self.config() | {"pin": "1234"}, "Unknown keys"),
		):
			with self.subTest(text), self.assertRaises(CertificateError) as caught:
				self.certificate(config)
			self.assertIn(text, str(caught.exception))

	def test_the_pin_is_stored_encrypted_and_never_in_the_config(self):
		doc = self.certificate()
		self.assertNotIn(self.token.pin, doc.remote_config)
		self.assertEqual(doc.get_password("remote_pin"), self.token.pin)
		self.assertNotEqual(frappe.db.get_value("Sign Certificate", doc.name, "remote_pin"), self.token.pin)


class TestSigner(RemoteCase):
	def test_the_seal_job_gets_a_remote_signer_for_a_remote_profile_certificate(self):
		company = test_company()
		certificate = self.certificate()
		make_profile(company, sealing_certificate=certificate.name)
		signer = sealing.sealing_signer(company)
		self.assertIsInstance(signer, RemoteSigner)
		self.assertTrue(any("Frappe Sign Test Seal" in c.subject.human_friendly for c in signer.chain()))

	def test_the_site_can_limit_the_libraries(self):
		certificate = self.certificate()
		self.addCleanup(frappe.conf.pop, "frappe_sign_pkcs11_modules", None)
		frappe.conf["frappe_sign_pkcs11_modules"] = ["/usr/lib/other.so"]
		with self.assertRaises(CertificateError):
			certificates.remote_signer(certificate.name)
		frappe.conf["frappe_sign_pkcs11_modules"] = [self.token.module_path]
		self.assertIsInstance(certificates.remote_signer(certificate.name), RemoteSigner)


class TestRefresh(RemoteCase):
	def test_reading_the_certificate_fills_in_its_details(self):
		certificate = self.certificate()
		details = certificates.refresh_remote(certificate.name)
		self.assertIn("Frappe Sign Test Seal", details["subject"])
		doc = frappe.get_doc("Sign Certificate", certificate.name)
		self.assertEqual(doc.valid_to.year, 2041)
		self.assertEqual(len(doc.fingerprint_sha256), 64)

	def test_only_a_system_manager_may_read_it(self):
		certificate = self.certificate()
		make_user("remote-manager@example.com", "Sign Manager")
		with self.as_user("remote-manager@example.com"), self.assertRaises(frappe.PermissionError):
			certificates.refresh_remote(certificate.name)

	def test_a_file_certificate_is_not_read_this_way(self):
		from frappe_sign.tests.factories import make_certificate

		with self.assertRaises(CertificateError):
			certificates.refresh_remote(make_certificate().name)

	def test_the_daily_job_reads_every_remote_certificate_and_logs_failures(self):
		good = self.certificate()
		bad = self.certificate(self.config(key_label="missing"))
		self.assertCountEqual(
			[name for name in schedule.refresh_remote_certificates() if name in (good.name, bad.name)],
			[good.name],
		)
		self.assertTrue(frappe.db.exists("Error Log", {"reference_name": bad.name}))
