"""Security review (P3.8): controls of DESIGN section 5 that had no test of their own."""

import json

import frappe
from frappe.utils import set_request

from frappe_sign.api import public
from frappe_sign.exceptions import FrappeSignError
from frappe_sign.services import signing
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.integration.test_signing_service import CLIENT, SigningCase
from frappe_sign.tests.security.test_guest_api import random_ip


class TestPermissionsAreAsDesigned(SignTestCase):
	def test_no_role_may_create_a_sign_event(self):
		"""5.5: nobody can add events through the REST API; services/audit.py inserts them."""
		for perm in frappe.get_meta("Sign Event").permissions:
			self.assertFalse(perm.create, f"{perm.role} may create Sign Events")

	def test_a_sign_manager_may_only_select_a_sign_certificate(self):
		"""2.1: a Profile can link a certificate, but nobody below System Manager can read it."""
		for perm in frappe.get_meta("Sign Certificate").permissions:
			if perm.role == "Sign Manager":
				self.assertTrue(perm.select)
				for right in ("read", "write", "create", "delete", "export", "print", "email", "share"):
					self.assertFalse(perm.get(right), f"Sign Manager has {right} on Sign Certificate")

	def test_certificate_secret_fields_are_passwords(self):
		meta = frappe.get_meta("Sign Certificate")
		for fieldname in ("p12_password", "remote_pin", "remote_token"):
			self.assertEqual(meta.get_field(fieldname).fieldtype, "Password", fieldname)


class TestPublicVerifyIsRateLimited(SignTestCase):
	def call(self, ip: str):
		self.addCleanup(self.end_request)
		with self.as_user("Guest"):
			set_request(method="POST", path="/api/method/frappe_sign.api.public.verify")
			frappe.local.request_ip = ip
			frappe.local.form_dict = frappe._dict(
				cmd="frappe_sign.api.public.verify", envelope="SIGN-1999-99999"
			)
			frappe.local.response = frappe._dict()
			return public.verify(envelope="SIGN-1999-99999")

	def end_request(self):
		frappe.local.request = None
		frappe.local.request_ip = None
		frappe.local.form_dict = frappe._dict()

	def test_ten_a_minute_per_ip(self):
		"""5.6: the verify page is rate limited, and an unknown ID reveals nothing."""
		ip = random_ip()
		for _ in range(10):
			result = self.call(ip)
			self.assertEqual(result["found"], False)
			self.assertEqual(set(result) & {"signers", "title", "recipients", "reference_name"}, set())
		self.assertRaises(frappe.RateLimitExceededError, self.call, ip)
		try:
			self.call(random_ip())
		except FrappeSignError:
			self.fail("another address is not limited")


class TestConsentIsRecorded(SigningCase):
	def test_the_event_names_the_disclosure_version_the_signer_accepted(self):
		"""5.1 step 4: `consent_version` is recorded in the Consented event."""
		self.sent()
		opened = signing.open(self.token("Customer"), CLIENT)
		signing.consent(opened["session"], opened["consent"]["version"], CLIENT)
		payload = frappe.get_all(
			"Sign Event", filters={"envelope": self.name, "event": "Consented"}, pluck="payload"
		)[0]
		self.assertEqual(json.loads(payload), {"consent_version": opened["consent"]["version"]})


class TestPublicUploadCap(SignTestCase):
	def test_a_file_over_25_mb_is_refused_before_it_is_parsed(self):
		"""5.6: the anonymous upload is capped."""
		import base64

		from frappe_sign.exceptions import FieldValidationError

		big = base64.b64encode(b"%PDF-1.7\n" + b"0" * (public.MAX_UPLOAD + 1)).decode()
		with self.as_user("Guest"), self.assertRaises(FieldValidationError):
			public.read_upload(big)
