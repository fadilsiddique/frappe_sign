# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.exceptions import FieldValidationError

DATE_FIELDTYPES = ("Date", "Datetime")


class SignTrigger(Document):
	"""Rule that creates or sends an envelope when a source document event happens (D8)."""

	def validate(self):
		self.validate_event_details()
		self.validate_template_doctype()
		self.validate_condition()

	def validate_event_details(self):
		meta = frappe.get_meta(self.reference_doctype)
		if meta.istable or meta.issingle or meta.module == "Frappe Sign":
			frappe.throw(
				_("DocType {0} cannot have Sign Triggers.").format(self.reference_doctype),
				FieldValidationError,
			)
		if self.event == "Submit" and not meta.is_submittable:
			frappe.throw(
				_("DocType {0} is not submittable.").format(self.reference_doctype), FieldValidationError
			)
		if self.event == "Workflow State" and not self.workflow_state:
			frappe.throw(_("Set the workflow state to watch."), FieldValidationError)
		if self.event == "Value Change":
			self.require_field(meta, self.watch_field, _("Watch Field"))
		if self.event == "Date":
			field = self.require_field(meta, self.date_field, _("Date Field"))
			if field.fieldtype not in DATE_FIELDTYPES:
				frappe.throw(_("{0} is not a date field.").format(self.date_field), FieldValidationError)

	def require_field(self, meta, fieldname, label):
		field = meta.get_field(fieldname) if fieldname else None
		if not field:
			frappe.throw(
				_("{0}: {1} is not a field of {2}.").format(label, fieldname or "", self.reference_doctype),
				FieldValidationError,
			)
		return field

	def validate_template_doctype(self):
		template_doctype = frappe.db.get_value("Sign Template", self.template, "reference_doctype")
		if template_doctype and template_doctype != self.reference_doctype:
			frappe.throw(
				_("Template {0} is for {1}, not {2}.").format(
					self.template, template_doctype, self.reference_doctype
				),
				FieldValidationError,
			)

	def validate_condition(self):
		if not self.condition:
			return
		try:
			compile(self.condition, "<sign trigger condition>", "eval")
		except SyntaxError as error:
			frappe.throw(
				_("Condition is not a valid expression ({0}).").format(error.msg), FieldValidationError
			)
