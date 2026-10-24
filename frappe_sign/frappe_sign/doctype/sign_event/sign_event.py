# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.utils.integrity import reject_delete, reject_update, require_sha256


class SignEvent(Document):
	"""One link of an envelope's hash-chained audit log. Insert-only (DESIGN 2.6, 5.5)."""

	def before_validate(self):
		reject_update(self)
		require_sha256(self, "prev_hash", "hash")

	def validate(self):
		if cint(self.seq) < 1:
			frappe.throw(_("Sequence must start at 1."), FieldValidationError)

	def on_trash(self):
		reject_delete(self)


def on_doctype_update():
	# A second event with the same seq would fork the chain; the database refuses it.
	frappe.db.add_unique("Sign Event", ["envelope", "seq"], constraint_name="unique_envelope_seq")
