# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from frappe_sign.utils.integrity import require_private_files


class SignProfile(Document):
	"""Sealing certificate, branding and sender for one Company (D12)."""

	def before_validate(self):
		require_private_files(self, "stamp_image")
