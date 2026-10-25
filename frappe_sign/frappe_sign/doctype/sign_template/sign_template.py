# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.utils.integrity import require_private_files, validate_placed_field

PRINT_FORMAT = "Print Format"
UPLOADED_PDF = "Uploaded PDF"
# Approvers approve by finishing and CC recipients only receive copies, so neither owns fields.
ROLE_KINDS_WITH_FIELDS = ("Signer",)


class SignTemplate(Document):
	def before_validate(self):
		require_private_files(self, "pdf_file")

	def validate(self):
		self.validate_source()
		self.validate_roles()
		self.validate_fields()
		self.validate_published_version()

	def validate_source(self):
		if self.source_type == PRINT_FORMAT:
			if not self.reference_doctype:
				frappe.throw(_("Set the DocType for a Print Format template."), FieldValidationError)
			format_doctype = self.print_format and frappe.db.get_value(
				"Print Format", self.print_format, "doc_type"
			)
			if format_doctype and format_doctype != self.reference_doctype:
				frappe.throw(
					_("Print Format {0} is for {1}, not {2}.").format(
						self.print_format, format_doctype, self.reference_doctype
					),
					FieldValidationError,
				)

	def validate_roles(self):
		seen = set()
		for role in self.roles:
			if role.role_label in seen:
				frappe.throw(_("Role {0} is listed twice.").format(role.role_label), FieldValidationError)
			seen.add(role.role_label)
			if role.signer_source == "Doc Field" and not role.source_field:
				frappe.throw(
					_("Role {0}: set the source field.").format(role.role_label), FieldValidationError
				)

	def validate_fields(self):
		kinds = {role.role_label: role.kind for role in self.roles}
		seen = set()
		for field in self.fields:
			if field.field_key in seen:
				frappe.throw(_("Field key {0} is used twice.").format(field.field_key), FieldValidationError)
			seen.add(field.field_key)
			if field.role_label not in kinds:
				frappe.throw(
					_("Field {0}: role {1} is not in the roles table.").format(
						field.field_key, field.role_label
					),
					FieldValidationError,
				)
			if kinds[field.role_label] not in ROLE_KINDS_WITH_FIELDS:
				frappe.throw(
					_("Field {0}: role {1} is an {2} and cannot have fields.").format(
						field.field_key, field.role_label, _(kinds[field.role_label])
					),
					FieldValidationError,
				)
			validate_placed_field(field)

	def validate_published_version(self):
		if not self.published_version:
			return
		version_template = frappe.db.get_value("Sign Template Version", self.published_version, "template")
		if version_template != self.name:
			frappe.throw(
				_("Version {0} does not belong to this template.").format(self.published_version),
				FieldValidationError,
			)
