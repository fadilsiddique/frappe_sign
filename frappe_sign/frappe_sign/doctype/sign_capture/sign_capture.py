# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from frappe_sign.utils.integrity import reject_delete, reject_update, require_private_files, require_sha256


class SignCapture(Document):
	"""A drawn, typed or uploaded signature image. Insert-only (DESIGN 2.6)."""

	def before_validate(self):
		reject_update(self)
		require_sha256(self, "sha256")
		require_private_files(self, "image")

	def on_trash(self):
		reject_delete(self)
