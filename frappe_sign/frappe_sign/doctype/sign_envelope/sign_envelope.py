# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.exceptions import ImmutableRecord, InvalidTransition
from frappe_sign.utils.integrity import (
	changed_fields,
	require_sha256,
	validate_placed_field,
)

DRAFT = "Draft"
# Initial values of the service-owned fields. Any other service-owned field starts empty.
INITIAL_VALUES = {"status": DRAFT, "send_state": "Not Started", "sealing_state": "Not Started"}

# Set only by services, through db_set (DESIGN 2.6). save() may not change them.
SERVICE_FIELDS = (
	"status",
	"send_state",
	"send_error",
	"sealing_state",
	"source_changed",
	"original_file",
	"original_sha256",
	"signed_file",
	"signed_sha256",
	"audit_head",
	"sent_on",
	"expires_on",
	"completed_on",
	"void_reason",
)
RECIPIENT_INITIAL_VALUES = {"status": "Pending"}
RECIPIENT_SERVICE_FIELDS = (
	"status",
	"token_hash",
	"token_expires_on",
	"viewed_on",
	"signed_on",
	"intermediate_file",
	"intermediate_sha256",
	"decline_reason",
	"delegated_to",
)
FIELD_SERVICE_FIELDS = ("capture", "filled_on")


class SignEnvelope(Document):
	"""An envelope can be edited only while it is a Draft that is not being sent.

	After that, services change it with db_set and insert child rows directly (DESIGN 2.6).
	"""

	def before_validate(self):
		if self.is_new():
			if self.status != DRAFT:
				frappe.throw(_("A new Sign Envelope starts as a Draft."), InvalidTransition)
			reject_non_initial(self, SERVICE_FIELDS, INITIAL_VALUES)
		else:
			self.reject_edit_after_draft()
		# Rows saved with the parent belong to a Draft, so nothing has happened to them yet.
		for row in self.recipients:
			reject_non_initial(row, RECIPIENT_SERVICE_FIELDS, RECIPIENT_INITIAL_VALUES)
		for row in self.fields:
			reject_non_initial(row, FIELD_SERVICE_FIELDS, {})
		require_sha256(self, "original_sha256", "signed_sha256", "audit_head")

	def validate(self):
		for row in self.fields:
			validate_placed_field(row)

	def on_trash(self):
		if self.status != DRAFT:
			frappe.throw(
				_("Sign Envelope {0} is {1}. Only Draft envelopes can be deleted.").format(
					self.name, _(self.status)
				),
				ImmutableRecord,
			)

	def reject_edit_after_draft(self):
		before = self.get_doc_before_save()
		if before.status != DRAFT:
			frappe.throw(
				_("Sign Envelope {0} is {1}. Only Draft envelopes can be edited.").format(
					self.name, _(before.status)
				),
				ImmutableRecord,
			)
		if before.send_state == "Queued":
			frappe.throw(
				_("Sign Envelope {0} is being sent and cannot be edited.").format(self.name),
				ImmutableRecord,
			)
		changed = changed_fields(self, before, SERVICE_FIELDS)
		if "status" in changed:
			frappe.throw(
				_("Envelope status changes only through Frappe Sign actions such as Send or Void."),
				InvalidTransition,
			)
		if changed:
			raise_service_fields(self, changed)


def reject_non_initial(doc, fieldnames, initial_values):
	"""Each service-owned field must be empty or hold its initial value."""
	wrong = [
		fieldname
		for fieldname in fieldnames
		if doc.get(fieldname) and doc.get(fieldname) != initial_values.get(fieldname)
	]
	if wrong:
		raise_service_fields(doc, wrong)


def raise_service_fields(doc, fieldnames):
	labels = ", ".join(_(doc.meta.get_label(fieldname)) for fieldname in fieldnames)
	frappe.throw(
		_("{0}: set by Frappe Sign, cannot be changed directly.").format(labels),
		ImmutableRecord,
	)


def on_doctype_update():
	frappe.db.add_index("Sign Envelope", ["reference_doctype", "reference_name"])
	frappe.db.add_index("Sign Envelope", ["party_type", "party"])
