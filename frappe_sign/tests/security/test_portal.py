"""Portal "My Documents" (P3.4): a contact sees and downloads only their own signed documents."""

import json

import frappe

from frappe_sign.api import portal as portal_api
from frappe_sign.exceptions import FieldValidationError
from frappe_sign.services import portal
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf, make_private_file, make_user
from frappe_sign.tests.signing_helpers import COMPANY, CUSTOMER, make_draft

AHMED = CUSTOMER["email"]
FATIMA = COMPANY["email"]
OUTSIDER = "outsider@example.com"


class PortalCase(SignTestCase):
	def setUp(self):
		super().setUp()
		for email in (AHMED, FATIMA, OUTSIDER):
			make_user(email)
		self.signed = self.completed(recipients=[CUSTOMER, COMPANY])
		self.company_only = self.completed(recipients=[{**CUSTOMER, "email": "other@example.com"}, COMPANY])

	def completed(self, recipients, status="Completed", signed=True):
		draft = make_draft(recipients=recipients)
		file = make_private_file(f"{draft.name}.pdf", fixture_pdf())
		frappe.db.set_value("Sign Envelope", draft.name, {"status": status, "signed_file": file.name})
		for row in draft.recipients:
			frappe.db.set_value("Sign Envelope Recipient", row.name, "status", "Signed" if signed else "Sent")
		return draft.name

	def names(self, user):
		return [row["name"] for row in portal.signed_documents(user)]


class TestList(PortalCase):
	def test_lists_only_the_users_own_completed_documents(self):
		self.assertEqual(self.names(AHMED), [self.signed])
		self.assertCountEqual(self.names(FATIMA), [self.signed, self.company_only])
		self.assertEqual(self.names(OUTSIDER), [])

	def test_ignores_unfinished_voided_and_unsigned(self):
		for status in ("In Progress", "Voided", "Expired", "Declined"):
			self.completed(recipients=[CUSTOMER, COMPANY], status=status)
		self.completed(recipients=[CUSTOMER, COMPANY], signed=False)
		self.assertEqual(self.names(AHMED), [self.signed])

	def test_email_match_ignores_case_and_guest_gets_nothing(self):
		frappe.db.set_value("User", AHMED, "email", AHMED.upper())
		self.assertEqual(self.names(AHMED), [self.signed])
		self.assertEqual(portal.signed_documents("Guest"), [])

	def test_row_shape_has_no_other_recipients_or_source_document(self):
		row = portal.signed_documents(AHMED)[0]
		self.assertEqual(set(row), {"name", "title", "company", "completed_on"})


class TestDownload(PortalCase):
	def test_owner_downloads_and_the_event_is_recorded(self):
		with self.as_user(AHMED):
			data, file_name = portal.download(self.signed)
		self.assertTrue(data.startswith(b"%PDF"))
		self.assertEqual(file_name, f"{self.signed}-signed.pdf")
		events = frappe.get_all(
			"Sign Event",
			filters={"envelope": self.signed, "event": "Downloaded"},
			fields=["actor", "payload"],
		)
		self.assertEqual(events[0].actor, AHMED)
		self.assertEqual(json.loads(events[0].payload)["channel"], "portal")

	def test_someone_else_gets_a_permission_error_for_a_real_and_a_made_up_name(self):
		with self.as_user(OUTSIDER):
			self.assertRaises(frappe.PermissionError, portal.download, self.signed)
			self.assertRaises(frappe.PermissionError, portal.download, "SIGN-2099-99999")
		with self.as_user(AHMED):
			self.assertRaises(frappe.PermissionError, portal.download, self.company_only)

	def test_guest_cannot_call_the_endpoint(self):
		self.assertNotIn(portal_api.download, frappe.guest_methods)
		with self.as_user("Guest"):
			self.assertRaises(frappe.PermissionError, portal.download, self.signed)

	def test_unfinished_document_is_not_downloadable(self):
		name = self.completed(recipients=[CUSTOMER, COMPANY], status="In Progress")
		with self.as_user(AHMED):
			self.assertRaises(frappe.PermissionError, portal.download, name)

	def test_envelope_name_is_validated(self):
		with self.as_user(AHMED):
			self.assertRaises(FieldValidationError, portal.download, "x" * 200)


class TestPage(PortalCase):
	def test_guest_is_sent_to_login_and_a_user_gets_only_their_documents(self):
		from frappe_sign.www import my_signatures

		with self.as_user("Guest"):
			self.assertRaises(frappe.Redirect, my_signatures.get_context, frappe._dict())
		with self.as_user(AHMED):
			context = frappe._dict()
			my_signatures.get_context(context)
		self.assertEqual([row["name"] for row in context.documents], [self.signed])
