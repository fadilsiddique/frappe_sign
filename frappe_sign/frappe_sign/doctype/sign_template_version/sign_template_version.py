# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.utils.integrity import reject_delete, reject_update, require_sha256


class SignTemplateVersion(Document):
	"""Snapshot of a template at publish time. Envelopes link here, never to the live template.

	Insert-only (DESIGN 2.6).
	"""

	def before_validate(self):
		reject_update(self)
		require_sha256(self, "source_sha256")

	def validate(self):
		if cint(self.version_no) < 1:
			frappe.throw(_("Version must start at 1."), FieldValidationError)

	def on_trash(self):
		reject_delete(self)
