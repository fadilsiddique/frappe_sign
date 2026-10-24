# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document

from frappe_sign.utils.integrity import require_sha256


class SignSession(Document):
	"""A guest signing session. Holds only hashes of the session secret and the OTP (D10)."""

	def before_validate(self):
		require_sha256(self, "session_hash", "otp_hash")
