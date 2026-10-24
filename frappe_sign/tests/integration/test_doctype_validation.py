"""Validation in the DocType controllers other than the 2.6 integrity rules."""

import frappe
from frappe.tests import IntegrationTestCase

from frappe_sign.exceptions import CertificateError, FieldValidationError
from frappe_sign.tests.factories import (
	PRIVATE_PNG,
	make_envelope,
	make_template,
	make_template_version,
	signature_field,
)


class TestTemplateValidation(IntegrationTestCase):
	def test_valid_template_saves(self):
		self.assertTrue(make_template().name)

	def test_field_keys_are_unique(self):
		fields = [signature_field(), signature_field(y=0.5)]
		self.assertRaises(FieldValidationError, make_template, fields=fields)

	def test_field_role_must_exist(self):
		self.assertRaises(FieldValidationError, make_template, fields=[signature_field(role_label="Witness")])

	def test_approver_and_cc_have_no_fields(self):
		for kind in ("Approver", "CC"):
			roles = [{"role_label": "Customer", "kind": kind, "signer_source": "Ask at Send"}]
			self.assertRaises(FieldValidationError, make_template, roles=roles)

	def test_roles_are_unique_and_complete(self):
		role = {"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send"}
		self.assertRaises(FieldValidationError, make_template, roles=[role, role])
		fixed = {**role, "signer_source": "Fixed User"}
		self.assertRaises(FieldValidationError, make_template, roles=[fixed])
		doc_field = {**role, "signer_source": "Doc Field"}
		self.assertRaises(FieldValidationError, make_template, roles=[doc_field])

	def test_field_shapes(self):
		bad_fields = {
			"outside page": signature_field(y=0.95, h=0.1),
			"zero width": signature_field(w=0),
			"negative page": signature_field(page=-1),
			"anchor page without tag": signature_field(page=0),
			"dropdown without options": signature_field(field_type="Dropdown"),
			"bad regex": signature_field(field_type="Text", validation_regex="[unclosed"),
			"zero font": signature_field(font_size=0),
		}
		for case, field in bad_fields.items():
			with self.subTest(case=case):
				self.assertRaises(FieldValidationError, make_template, fields=[field])

	def test_anchor_field_and_page_edge_are_valid(self):
		fields = [
			signature_field(page=0, x=0, y=0, w=0, h=0, anchor_tag="[[fs:Customer:signature:1]]"),
			signature_field(field_key="edge", x=0.7, y=0.9, w=0.3, h=0.1),
		]
		self.assertTrue(make_template(fields=fields).name)

	def test_coordinates_keep_nine_decimals(self):
		template = make_template(fields=[signature_field(x=0.123456789)])
		stored = frappe.db.get_value("Sign Template Field", template.fields[0].name, "x")
		self.assertAlmostEqual(stored, 0.123456789, places=9)

	def test_sources_need_their_inputs(self):
		self.assertRaises(
			FieldValidationError, make_template, source_type="Print Format", reference_doctype=None
		)
		self.assertRaises(FieldValidationError, make_template, pdf_file=None)
		self.assertRaises(FieldValidationError, make_template, pdf_file="/files/public.pdf")

	def test_published_version_belongs_to_template(self):
		other_version = make_template_version()
		template = make_template()
		template.published_version = other_version.name
		self.assertRaises(FieldValidationError, template.save)


class TestSettingsValidation(IntegrationTestCase):
	def setUp(self):
		self.settings = frappe.get_single("Sign Settings")

	def test_consent_version_goes_up_when_text_changes(self):
		start = self.settings.consent_version or 0
		self.settings.consent_text = "<p>I agree to sign electronically.</p>"
		self.settings.save()
		self.assertEqual(self.settings.consent_version, start + 1)

		self.settings.default_expiry_days = 30
		self.settings.consent_version = 99
		self.settings.save()
		self.assertEqual(self.settings.consent_version, start + 1)

	def test_numbers_must_be_positive(self):
		self.settings.max_pages = 0
		self.assertRaises(FieldValidationError, self.settings.save)

	def test_reminders_can_be_switched_off(self):
		self.settings.default_reminder_days = 0
		self.settings.save()

	def test_tsa_urls_must_be_http(self):
		self.settings.tsa_urls = "http://timestamp.example.com\nftp://bad.example.com"
		self.assertRaises(FieldValidationError, self.settings.save)

	def test_enabled_doctypes(self):
		self.settings.append("enabled_doctypes", {"reference_doctype": "ToDo"})
		self.settings.save()
		self.settings.append("enabled_doctypes", {"reference_doctype": "ToDo"})
		self.assertRaises(FieldValidationError, self.settings.save)

		self.settings.reload()
		self.settings.append("enabled_doctypes", {"reference_doctype": "Sign Envelope"})
		self.assertRaises(FieldValidationError, self.settings.save)


class TestTriggerValidation(IntegrationTestCase):
	def make_trigger(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Sign Trigger",
				"reference_doctype": "ToDo",
				"event": "Save",
				"template": make_template().name,
				**values,
			}
		).insert()

	def test_valid_trigger_saves(self):
		self.assertTrue(self.make_trigger(condition="doc.status == 'Open'").name)

	def test_event_details(self):
		self.assertRaises(FieldValidationError, self.make_trigger, event="Submit")
		self.assertRaises(FieldValidationError, self.make_trigger, event="Value Change", watch_field="nope")
		self.assertRaises(FieldValidationError, self.make_trigger, event="Date", date_field="description")
		self.assertTrue(self.make_trigger(event="Date", date_field="date", days_offset=-3).name)

	def test_condition_must_parse(self):
		self.assertRaises(FieldValidationError, self.make_trigger, condition="doc.status ==")

	def test_template_doctype_must_match(self):
		template = make_template(source_type="Print Format", reference_doctype="Note", pdf_file=None)
		self.assertRaises(FieldValidationError, self.make_trigger, template=template.name)


class TestOtherValidation(IntegrationTestCase):
	def test_saved_signature_belongs_to_owner(self):
		values = {"doctype": "Sign Saved Signature", "kind": "Signature", "image": PRIVATE_PNG}
		self.assertEqual(frappe.get_doc(values).insert().user, frappe.session.user)
		other = frappe.get_doc({**values, "user": "Guest"})
		self.assertRaises(frappe.PermissionError, other.insert)
		public = frappe.get_doc({**values, "image": "/files/sig.png"})
		self.assertRaises(FieldValidationError, public.insert)

	def test_profile_stamp_must_be_private(self):
		profile = frappe.get_doc(
			{"doctype": "Sign Profile", "company": "Test Company", "stamp_image": "/files/stamp.png"}
		)
		self.assertRaises(FieldValidationError, profile.insert)

	def test_certificate_storage(self):
		values = {"doctype": "Sign Certificate", "title": "Test Seal", "p12_password": "secret"}
		remote = frappe.get_doc({**values, "storage": "Remote"})
		self.assertRaises(CertificateError, remote.insert)
		public = frappe.get_doc({**values, "p12_file": "/files/seal.p12"})
		self.assertRaises(FieldValidationError, public.insert)

	def test_envelope_sender_defaults_to_session_user(self):
		self.assertEqual(make_envelope().sender, frappe.session.user)
