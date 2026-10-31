"""DESIGN 5.3: sealing key material exists only inside the seal job. The public verify path reads
the certificate chain stored on the Sign Certificate and never decrypts a password or opens a token."""

from unittest.mock import patch

import frappe

from frappe_sign.crypto import pkcs12
from frappe_sign.services import certificates, sealing, verify
from frappe_sign.tests import pki
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_certificate, make_envelope, make_profile, test_company


class TestPublicChain(SignTestCase):
	def test_saving_a_p12_stores_its_certificates_and_no_key(self):
		certificate = make_certificate()
		chain = frappe.db.get_value("Sign Certificate", certificate.name, "public_chain")
		self.assertEqual(chain.count("BEGIN CERTIFICATE"), 2)
		self.assertNotIn("PRIVATE KEY", chain)

	def test_public_chain_pem_helper(self):
		pem = pkcs12.public_chain_pem((pki.CERTS / "sealing.p12").read_bytes(), pki.P12_PASSWORD)
		self.assertEqual(pem.count("BEGIN CERTIFICATE"), 2)
		self.assertNotIn("PRIVATE KEY", pem)

	def test_trusted_roots_come_from_the_stored_chain(self):
		company = test_company()
		make_profile(company)
		roots = certificates.trusted_roots(company)
		self.assertEqual(
			[cert.subject.human_friendly for cert in roots], [pki.root_cert().subject.human_friendly]
		)

	def test_verify_trust_never_decrypts_or_opens_the_signer(self):
		company = test_company()
		make_profile(company)
		envelope = make_envelope(company=company)
		with (
			patch(
				"frappe_sign.services.certificates.get_decrypted_password",
				side_effect=AssertionError("decrypted"),
			),
			patch.object(sealing, "sealing_signer", side_effect=AssertionError("signer opened")),
		):
			context = verify.trust_context(envelope.name)
		self.assertTrue(context)
		self.assertFalse(frappe.db.exists("Error Log", {"method": "Frappe Sign: verify trust roots"}))

	def test_a_certificate_without_a_stored_chain_trusts_nothing_extra(self):
		company = test_company()
		profile = make_profile(company)
		frappe.db.set_value("Sign Certificate", profile.sealing_certificate, "public_chain", None)
		self.assertEqual(certificates.trusted_roots(company), [])


class TestPatch(SignTestCase):
	def test_the_patch_fills_in_certificates_saved_before_the_field_existed(self):
		from frappe_sign.patches.v1_0 import store_public_chain

		certificate = make_certificate()
		frappe.db.set_value("Sign Certificate", certificate.name, "public_chain", None)
		store_public_chain.execute()
		self.assertEqual(
			frappe.db.get_value("Sign Certificate", certificate.name, "public_chain").count(
				"BEGIN CERTIFICATE"
			),
			2,
		)
