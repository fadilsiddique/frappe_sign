# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class SignTriggerLog(Document):
	pass


def on_doctype_update():
	# Trigger runs are listed on the source document (D8).
	frappe.db.add_index("Sign Trigger Log", ["reference_doctype", "reference_name"])
