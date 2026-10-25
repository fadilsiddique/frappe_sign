"""services/template.py (P1.7): create, update, upload PDF, publish an immutable version."""

import json

import frappe

from frappe_sign.exceptions import FieldValidationError, ImmutableRecord
from frappe_sign.services import template as template_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf, make_user, signature_field
from frappe_sign.utils.files import read_file_url
from frappe_sign.utils.hashing import sha256_hex

MANAGER = "sign.manager@example.com"
SIGN_USER = "sign.user@example.com"


def template_data(**overrides) -> dict:
	return {
		"title": "NDA",
		"source_type": "Uploaded PDF",
		"signing_order": "Sequential",
		"roles": [
			{"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send", "routing_order": 1},
			{"role_label": "Company", "kind": "Signer", "signer_source": "Ask at Send", "routing_order": 2},
		],
		"fields": [
			signature_field(),
			signature_field(field_key="company_signature", role_label="Company", y=0.9),
		],
		**overrides,
	}


class TestTemplateService(SignTestCase):
	def setUp(self):
		super().setUp()
		make_user(MANAGER, "Sign Manager")
		make_user(SIGN_USER, "Sign User")

	def new_template(self, pdf: str = "a4_simple.pdf", **overrides):
		with self.as_user(MANAGER):
			template = template_service.create_template(template_data(**overrides))
			template_service.upload_pdf(template.name, "nda.pdf", fixture_pdf(pdf))
		return frappe.get_doc("Sign Template", template.name)

	def test_upload_sanitizes_stores_privately_and_measures(self):
		template = self.new_template("rotated_270_cropbox.pdf")
		self.assertTrue(template.pdf_file.startswith("/private/files/"))
		metrics = json.loads(template.page_metrics)
		self.assertEqual(
			metrics,
			[{"page": 1, "width": 540.0, "height": 696.0, "rotation": 270, "left": 36.0, "bottom": 48.0}],
		)
		file = frappe.get_doc("File", {"file_url": template.pdf_file})
		self.assertEqual(
			(file.attached_to_doctype, file.attached_to_name, file.is_private),
			("Sign Template", template.name, 1),
		)

	def test_upload_strips_active_content(self):
		template = self.new_template("with_javascript.pdf")
		content = read_file_url(template.pdf_file)
		self.assertNotIn(b"/JavaScript", content)

	def test_upload_rejects_encrypted_and_oversized_pdfs(self):
		template = self.new_template()
		with self.as_user(MANAGER):
			with self.assertRaises(FieldValidationError):
				template_service.upload_pdf(template.name, "x.pdf", fixture_pdf("encrypted.pdf"))
			frappe.db.set_single_value("Sign Settings", "max_pages", 100)
			with self.assertRaises(FieldValidationError):
				template_service.upload_pdf(template.name, "x.pdf", fixture_pdf("many_pages_150.pdf"))

	def test_publish_snapshots_the_template(self):
		template = self.new_template()
		with self.as_user(MANAGER):
			version = template_service.publish(template.name)
		self.assertEqual(version.version_no, 1)
		self.assertEqual(
			frappe.db.get_value("Sign Template", template.name, "published_version"), version.name
		)
		snapshot = json.loads(version.snapshot)
		self.assertEqual([role["role_label"] for role in snapshot["roles"]], ["Customer", "Company"])
		self.assertEqual(
			[field["field_key"] for field in snapshot["fields"]], ["customer_signature", "company_signature"]
		)
		self.assertEqual(snapshot["pdf_file"], template.pdf_file)
		pdf = read_file_url(template.pdf_file)
		self.assertEqual(version.source_sha256, sha256_hex(pdf))

	def test_version_snapshot_is_immutable(self):
		template = self.new_template()
		with self.as_user(MANAGER):
			version = template_service.publish(template.name)
			template_service.update_template(
				template.name, {"title": "Changed", "fields": [signature_field(y=0.5)]}
			)
			second = template_service.publish(template.name)
		self.assertEqual(
			json.loads(frappe.db.get_value("Sign Template Version", version.name, "snapshot"))["title"], "NDA"
		)
		self.assertEqual(second.version_no, 2)
		self.assertEqual(json.loads(second.snapshot)["title"], "Changed")
		stored = frappe.get_doc("Sign Template Version", version.name)
		stored.snapshot = "{}"
		self.assertRaises(ImmutableRecord, stored.save)

	def test_publish_checks_the_template(self):
		template = self.new_template()
		with self.as_user(MANAGER):
			template_service.update_template(template.name, {"fields": [signature_field(page=2)]})
			self.assertRaises(FieldValidationError, template_service.publish, template.name)
		cc_only = {
			"roles": [{"role_label": "Customer", "kind": "CC", "signer_source": "Ask at Send"}],
			"fields": [],
		}
		template = self.new_template(**cc_only)
		with self.as_user(MANAGER):
			self.assertRaises(FieldValidationError, template_service.publish, template.name)

	def test_publish_needs_an_uploaded_pdf(self):
		with self.as_user(MANAGER):
			template = template_service.create_template(template_data())
			self.assertRaises(FieldValidationError, template_service.publish, template.name)

	def test_sign_user_cannot_create_or_publish(self):
		template = self.new_template()
		with self.as_user(SIGN_USER):
			self.assertRaises(frappe.PermissionError, template_service.create_template, template_data())
			self.assertRaises(frappe.PermissionError, template_service.publish, template.name)
			self.assertRaises(
				frappe.PermissionError, template_service.upload_pdf, template.name, "x.pdf", fixture_pdf()
			)

	def test_update_cannot_set_service_fields(self):
		template = self.new_template()
		with self.as_user(MANAGER):
			version = template_service.publish(template.name)
			template_service.update_template(
				template.name, {"published_version": None, "page_metrics": "[]", "title": "T2"}
			)
		template.reload()
		self.assertEqual((template.published_version, template.title), (version.name, "T2"))
		self.assertNotEqual(template.page_metrics, "[]")
