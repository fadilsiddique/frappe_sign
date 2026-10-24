import inspect

import frappe
from frappe.tests import UnitTestCase

from frappe_sign import exceptions

EXPECTED_STATUS = {
	"EnvelopeNotOpen": 409,
	"NotYourTurn": 409,
	"OtpRequired": 401,
	"OtpInvalid": 401,
	"LinkExpired": 410,
	"InvalidTransition": 409,
	"FieldValidationError": 422,
	"CertificateError": 500,
	"ImmutableRecord": 409,
}


def domain_errors() -> dict[str, type[exceptions.FrappeSignError]]:
	return {
		name: cls
		for name, cls in inspect.getmembers(exceptions, inspect.isclass)
		if issubclass(cls, exceptions.FrappeSignError) and cls is not exceptions.FrappeSignError
	}


class TestExceptions(UnitTestCase):
	def test_status_codes_match_design(self):
		statuses = {name: cls.http_status_code for name, cls in domain_errors().items()}
		self.assertEqual(statuses, EXPECTED_STATUS)

	def test_codes_are_stable_and_unique(self):
		codes = [cls.code for cls in domain_errors().values()]
		self.assertEqual(len(codes), len(set(codes)))
		self.assertNotIn(exceptions.FrappeSignError.code, codes)

	def test_errors_are_validation_errors(self):
		for cls in domain_errors().values():
			self.assertTrue(issubclass(cls, frappe.ValidationError), cls)

	def test_throw_raises_the_domain_error(self):
		with self.assertRaises(exceptions.OtpInvalid) as raised:
			frappe.throw(frappe._("Wrong code"), exc=exceptions.OtpInvalid)
		self.assertEqual(raised.exception.code, "otp_invalid")
