# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.exceptions import CertificateError
from frappe_sign.utils.integrity import require_private_files


class SignCertificate(Document):
	"""A sealing certificate. Only System Manager can read it; Sign Manager can only link it.

	Parsing and checking the PKCS#12 on save (DESIGN 2.1) arrives with crypto/pkcs12.py in Phase 1.
	"""

	def before_validate(self):
		require_private_files(self, "p12_file")

	def validate(self):
		if self.storage == "Remote":
			frappe.throw(
				_("Remote signing keys are not available yet. Use a PKCS#12 file."), CertificateError
			)
