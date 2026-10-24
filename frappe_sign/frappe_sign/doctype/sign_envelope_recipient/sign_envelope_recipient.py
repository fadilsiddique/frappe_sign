# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from frappe_sign.utils.integrity import require_sha256


class SignEnvelopeRecipient(Document):
	# Runs when a service inserts a row directly into a sent envelope, such as on delegation
	# (DESIGN 2.6). Rows saved with the parent are checked by the Sign Envelope controller.
	def before_validate(self):
		require_sha256(self, "token_hash", "intermediate_sha256")
