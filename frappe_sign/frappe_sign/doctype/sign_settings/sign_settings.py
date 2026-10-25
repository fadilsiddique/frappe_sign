# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from urllib.parse import urlparse

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from frappe_sign.exceptions import FieldValidationError

# Fields that must be at least 1. default_reminder_days may be 0 (reminders off).
POSITIVE_FIELDS = ("default_expiry_days", "otp_validity_minutes", "max_upload_mb", "max_pages")


class SignSettings(Document):
	def validate(self):
		self.validate_positive_numbers()
		self.validate_tsa_urls()
		self.validate_enabled_doctypes()
		self.set_consent_version()

	def validate_positive_numbers(self):
		for fieldname in POSITIVE_FIELDS:
			if cint(self.get(fieldname)) < 1:
				frappe.throw(
					_("{0} must be at least 1.").format(_(self.meta.get_label(fieldname))),
					FieldValidationError,
				)

	def validate_tsa_urls(self):
		for url in self.get_tsa_urls():
			parsed = urlparse(url)
			if parsed.scheme not in ("http", "https") or not parsed.netloc:
				frappe.throw(
					_("TSA URL {0} is not a valid http or https URL.").format(url), FieldValidationError
				)

	def get_tsa_urls(self) -> list[str]:
		return [line.strip() for line in (self.tsa_urls or "").splitlines() if line.strip()]

	def validate_enabled_doctypes(self):
		self.check_can_enable()
		seen = set()
		for row in self.enabled_doctypes:
			if row.reference_doctype in seen:
				frappe.throw(
					_("DocType {0} is listed twice.").format(row.reference_doctype), FieldValidationError
				)
			seen.add(row.reference_doctype)
			meta = frappe.get_meta(row.reference_doctype)
			if meta.istable or meta.issingle or meta.module == "Frappe Sign":
				frappe.throw(
					_("DocType {0} cannot be enabled for signing.").format(row.reference_doctype),
					FieldValidationError,
				)

	def check_can_enable(self):
		"""Enabling a DocType adds custom fields to it, which only a System Manager may do."""
		before = self.get_doc_before_save()
		previous = {row.reference_doctype for row in before.enabled_doctypes} if before else set()
		added = {row.reference_doctype for row in self.enabled_doctypes} - previous
		if added and "System Manager" not in frappe.get_roles():
			frappe.throw(
				_("Only a System Manager can enable DocTypes for signing: {0}.").format(
					", ".join(sorted(added))
				),
				frappe.PermissionError,
			)

	def set_consent_version(self):
		"""consent_version goes up by one each time the consent text changes (read only)."""
		before = self.get_doc_before_save()
		version = cint(before.consent_version) if before else 0
		if self.consent_text != (before.consent_text if before else None) and self.consent_text:
			version += 1
		self.consent_version = version
