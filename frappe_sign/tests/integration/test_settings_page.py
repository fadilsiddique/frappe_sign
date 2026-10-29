"""services/settings_page.py and the upload_certificate service (U.9, UX_PLAN "Settings")."""

from unittest.mock import patch

import frappe

from frappe_sign.api import staff
from frappe_sign.exceptions import CertificateError, FieldValidationError
from frappe_sign.services import certificates, doctypes, settings_page
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_profile, make_user, test_company
from frappe_sign.tests.pki import CERTS
from frappe_sign.tests.signing_helpers import publish_template

MANAGER = "settings-manager@example.com"
SIGN_USER = "settings-user@example.com"
HAS_ERPNEXT = "erpnext" in frappe.get_installed_apps()


def published_template() -> str:
	return frappe.db.get_value("Sign Template Version", publish_template(), "template")


class SettingsPageCase(SignTestCase):
	def setUp(self):
		super().setUp()
		make_user(MANAGER, "Sign Manager")
		make_user(SIGN_USER, "Sign User")
		frappe.db.delete("Sign Enabled DocType")
		# Enabling a DocType adds custom fields, a schema change that commits.
		patcher = patch.object(doctypes, "add_custom_fields")
		patcher.start()
		self.addCleanup(patcher.stop)

	def enable(self, doctype: str = "Note"):
		return settings_page.enable_doctype(doctype)


class TestOverview(SettingsPageCase):
	def test_a_sign_manager_sees_everything_but_cannot_edit(self):
		profile = make_profile()
		with self.as_user(MANAGER):
			data = settings_page.overview()
		self.assertFalse(data["can_edit"])
		card = next(card for card in data["profiles"] if card["company"] == profile.name)
		self.assertFalse(card["seal"]["expired"])
		self.assertEqual(card["brand_color"], "#0f766e")
		self.assertIn("default_expiry_days", data["signing"])
		self.assertIn("tsa_urls", data["advanced"])

	def test_a_system_manager_can_edit(self):
		self.assertTrue(settings_page.overview()["can_edit"])

	def test_a_sign_user_is_refused(self):
		with self.as_user(SIGN_USER):
			self.assertRaises(frappe.PermissionError, settings_page.overview)

	def test_the_seal_facts_carry_no_secret(self):
		make_profile()
		text = frappe.as_json(settings_page.overview())
		self.assertNotIn("fixture-seal", text)
		self.assertNotIn("p12", text)

	def test_documents_list_templates_and_sends(self):
		template = published_template()
		frappe.db.set_value("Sign Template", template, "reference_doctype", "Note")
		self.enable("Note")
		row = next(row for row in settings_page.overview()["documents"] if row["doctype"] == "Note")
		self.assertEqual([t["name"] for t in row["templates"]], [template])
		self.assertEqual(row["sends"], 0)

	def test_sender_status_is_missing_without_an_outgoing_account(self):
		profile = make_profile()
		frappe.db.delete("Email Account")
		card = next(card for card in settings_page.overview()["profiles"] if card["company"] == profile.name)
		self.assertEqual(card["sender"], {"status": "missing", "email_id": None})

	def test_sender_status_is_default_without_a_profile_account(self):
		profile = make_profile()
		card = next(card for card in settings_page.overview()["profiles"] if card["company"] == profile.name)
		self.assertEqual(card["sender"]["status"], "default")


class TestSaveProfile(SettingsPageCase):
	def test_creates_a_profile_for_a_company_without_one(self):
		company = test_company()
		frappe.db.delete("Sign Profile")
		card = settings_page.save_profile(company, {"brand_color": "#112233"})
		self.assertEqual(card["company"], company)
		self.assertEqual(frappe.db.get_value("Sign Profile", company, "brand_color"), "#112233")

	def test_changes_only_the_given_fields(self):
		profile = make_profile()
		settings_page.save_profile(profile.name, {"legal_footer": "Gulf Trading LLC"})
		values = frappe.db.get_value(
			"Sign Profile", profile.name, ["legal_footer", "brand_color", "sealing_certificate"], as_dict=True
		)
		self.assertEqual(values.legal_footer, "Gulf Trading LLC")
		self.assertEqual(values.brand_color, "#0f766e")
		self.assertEqual(values.sealing_certificate, profile.sealing_certificate)

	def test_an_empty_value_clears_the_field(self):
		profile = make_profile()
		settings_page.save_profile(profile.name, {"brand_color": ""})
		self.assertFalse(frappe.db.get_value("Sign Profile", profile.name, "brand_color"))

	def test_rejects_a_bad_color_and_unknown_fields(self):
		profile = make_profile()
		self.assertRaises(
			FieldValidationError, settings_page.save_profile, profile.name, {"brand_color": "teal"}
		)
		self.assertRaises(
			FieldValidationError, settings_page.save_profile, profile.name, {"sealing_certificate": "x"}
		)

	def test_a_sign_manager_cannot_change_it(self):
		profile = make_profile()
		with self.as_user(MANAGER):
			self.assertRaises(
				frappe.PermissionError, settings_page.save_profile, profile.name, {"brand_color": "#000000"}
			)
		self.assertEqual(frappe.db.get_value("Sign Profile", profile.name, "brand_color"), "#0f766e")


class TestSaveSettings(SettingsPageCase):
	def test_signing_and_advanced_values_are_saved(self):
		settings_page.save_settings(
			"signing", {"default_expiry_days": "30", "default_reminder_days": 0, "consent_text": "<p>Hi</p>"}
		)
		settings_page.save_settings("advanced", {"tsa_urls": "https://tsa.example.com/tsr", "max_pages": 50})
		self.assertEqual(frappe.db.get_single_value("Sign Settings", "default_expiry_days"), 30)
		self.assertEqual(frappe.db.get_single_value("Sign Settings", "consent_text"), "<p>Hi</p>")
		self.assertEqual(frappe.db.get_single_value("Sign Settings", "max_pages"), 50)

	def test_the_consent_version_goes_up_with_the_text(self):
		before = frappe.db.get_single_value("Sign Settings", "consent_version") or 0
		settings_page.save_settings("signing", {"consent_text": "<p>New words</p>"})
		self.assertEqual(frappe.db.get_single_value("Sign Settings", "consent_version"), before + 1)

	def test_the_documents_own_checks_still_apply(self):
		self.assertRaises(
			FieldValidationError, settings_page.save_settings, "signing", {"default_expiry_days": 0}
		)
		self.assertRaises(
			FieldValidationError, settings_page.save_settings, "advanced", {"tsa_urls": "not a url"}
		)

	def test_rejects_unknown_sections_and_fields(self):
		self.assertRaises(FieldValidationError, settings_page.save_settings, "other", {})
		self.assertRaises(FieldValidationError, settings_page.save_settings, "signing", {"max_pages": 5})

	def test_a_sign_manager_cannot_change_it(self):
		with self.as_user(MANAGER):
			self.assertRaises(
				frappe.PermissionError, settings_page.save_settings, "signing", {"default_expiry_days": 3}
			)


class TestDocuments(SettingsPageCase):
	def test_enable_then_disable(self):
		row = self.enable("Note")
		self.assertEqual(row["doctype"], "Note")
		self.assertIn("Note", doctypes.enabled_doctypes())
		settings_page.disable_doctype("Note")
		self.assertNotIn("Note", doctypes.enabled_doctypes())

	def test_enabling_adds_the_custom_fields(self):
		with patch.object(doctypes, "add_custom_fields") as add:
			self.enable("Note")
		add.assert_called_once_with(["Note"])

	def test_enabling_twice_or_disabling_a_missing_one_fails(self):
		self.enable("Note")
		self.assertRaises(FieldValidationError, self.enable, "Note")
		self.assertRaises(FieldValidationError, settings_page.disable_doctype, "ToDo")

	def test_our_own_and_child_doctypes_are_refused(self):
		self.assertRaises(FieldValidationError, self.enable, "Sign Envelope")
		self.assertRaises(FieldValidationError, self.enable, "Sign Enabled DocType")

	def test_default_template(self):
		template = published_template()
		frappe.db.set_value("Sign Template", template, "reference_doctype", "Note")
		self.enable("Note")
		row = settings_page.set_default_template("Note", template)
		self.assertEqual(row["default_template"], template)
		self.assertEqual(
			frappe.db.get_value(
				"Sign Enabled DocType",
				{"parent": "Sign Settings", "reference_doctype": "Note"},
				"default_template",
			),
			template,
		)
		self.assertIsNone(settings_page.set_default_template("Note", None)["default_template"])

	def test_default_template_must_match_the_doctype(self):
		template = published_template()
		self.enable("Note")
		self.assertRaises(FieldValidationError, settings_page.set_default_template, "Note", template)
		self.assertRaises(FieldValidationError, settings_page.set_default_template, "ToDo", None)

	def test_default_template_must_be_published(self):
		template = published_template()
		frappe.db.set_value(
			"Sign Template", template, {"reference_doctype": "Note", "published_version": None}
		)
		self.enable("Note")
		self.assertRaises(FieldValidationError, settings_page.set_default_template, "Note", template)

	def test_choices_leave_out_enabled_child_and_own_doctypes(self):
		self.enable("Note")
		choices = settings_page.doctype_choices("")
		self.assertNotIn("Note", choices)
		self.assertNotIn("Sign Envelope", choices)
		self.assertNotIn("Sign Enabled DocType", choices)
		self.assertEqual(settings_page.doctype_choices("ToDo"), ["ToDo"])

	def test_a_sign_manager_cannot_change_documents(self):
		with self.as_user(MANAGER):
			self.assertRaises(frappe.PermissionError, self.enable, "Note")
			self.assertRaises(frappe.PermissionError, settings_page.doctype_choices, "")

	def test_the_api_functions_reach_the_services(self):
		self.assertEqual(staff.enable_doctype("Note")["doctype"], "Note")
		self.assertEqual(staff.get_settings()["documents"][0]["doctype"], "Note")
		self.assertEqual(staff.disable_doctype("Note"), {"doctype": "Note"})


class TestUploadCertificate(SettingsPageCase):
	def p12(self) -> bytes:
		return (CERTS / "sealing.p12").read_bytes()

	def test_replaces_the_profile_seal_with_a_private_file(self):
		profile = make_profile()
		old = profile.sealing_certificate
		result = certificates.upload_certificate(
			profile.name, "company.p12", self.p12(), "fixture-seal", "AATL"
		)
		self.assertNotEqual(result["certificate"], old)
		self.assertEqual(result["profile_action"], "linked")
		self.assertEqual(
			frappe.db.get_value("Sign Profile", profile.name, "sealing_certificate"), result["certificate"]
		)
		certificate = frappe.get_doc("Sign Certificate", result["certificate"])
		self.assertEqual(certificate.kind, "AATL")
		file = frappe.get_doc("File", {"file_url": certificate.p12_file})
		self.assertEqual(file.is_private, 1)

	def test_creates_the_profile_when_the_company_has_none(self):
		company = test_company()
		frappe.db.delete("Sign Profile")
		result = certificates.upload_certificate(company, "a.p12", self.p12(), "fixture-seal")
		self.assertEqual(result["profile_action"], "created")

	def test_a_wrong_password_is_refused_and_nothing_is_kept(self):
		profile = make_profile()
		files = frappe.db.count("File")
		self.assertRaises(
			CertificateError, certificates.upload_certificate, profile.name, "a.p12", self.p12(), "nope"
		)
		self.assertEqual(
			frappe.db.get_value("Sign Profile", profile.name, "sealing_certificate"),
			profile.sealing_certificate,
		)
		self.assertEqual(frappe.db.count("Sign Certificate", {"title": ["like", f"{profile.name} (%"]}), 0)
		self.assertGreaterEqual(frappe.db.count("File"), files)

	def test_an_empty_file_and_a_bad_kind_are_refused(self):
		profile = make_profile()
		self.assertRaises(CertificateError, certificates.upload_certificate, profile.name, "a.p12", b"", "x")
		self.assertRaises(
			CertificateError,
			certificates.upload_certificate,
			profile.name,
			"a.p12",
			self.p12(),
			"fixture-seal",
			"Self-signed",
		)

	def test_a_sign_manager_cannot_upload(self):
		profile = make_profile()
		with self.as_user(MANAGER):
			self.assertRaises(
				frappe.PermissionError,
				certificates.upload_certificate,
				profile.name,
				"a.p12",
				self.p12(),
				"fixture-seal",
			)

	def test_the_test_seal_replaces_an_expired_one_only_when_asked(self):
		company = test_company()
		profile = make_profile(company)
		first = profile.sealing_certificate
		kept = certificates.create_test_certificate(company)
		self.assertIsNone(kept["profile_action"])
		self.assertEqual(frappe.db.get_value("Sign Profile", company, "sealing_certificate"), first)
		replaced = certificates.create_test_certificate(company, replace=True)
		self.assertEqual(replaced["profile_action"], "linked")
		self.assertEqual(
			frappe.db.get_value("Sign Profile", company, "sealing_certificate"), replaced["certificate"]
		)
