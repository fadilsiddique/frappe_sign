# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.utils.integrity import require_private_files


class SignSavedSignature(Document):
	"""A user's saved signature or initials. Visible to its owner only."""

	def before_validate(self):
		require_private_files(self, "image")

	def validate(self):
		if self.user != self.owner:
			frappe.throw(_("A saved signature belongs to the user who saved it."), frappe.PermissionError)
