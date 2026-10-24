"""Integrity rules from DESIGN 2.6."""

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from frappe_sign.exceptions import FieldValidationError, ImmutableRecord, InvalidTransition
from frappe_sign.tests.factories import (
	make_capture,
	make_envelope,
	make_event,
	make_template_version,
	signature_field,
)
from frappe_sign.utils.hashing import sha256_hex

INSERT_ONLY_DOCTYPES = ("Sign Event", "Sign Capture", "Sign Template Version")


class TestInsertOnlyRecords(IntegrationTestCase):
	def setUp(self):
		self.envelope = make_envelope()

	def test_no_role_may_write_or_delete(self):
		for doctype in INSERT_ONLY_DOCTYPES:
			for perm in frappe.get_meta(doctype).permissions:
				self.assertFalse(perm.write, f"{doctype}: {perm.role} has write")
				self.assertFalse(perm.delete, f"{doctype}: {perm.role} has delete")

	def test_records_cannot_be_changed(self):
		records = {
			"actor": make_event(self.envelope),
			"field_key": make_capture(self.envelope),
			"source_sha256": make_template_version(),
		}
		for fieldname, doc in records.items():
			with self.subTest(doctype=doc.doctype):
				doc.set(fieldname, sha256_hex(b"other"))
				self.assertRaises(ImmutableRecord, doc.save)

	def test_ignore_validate_does_not_bypass_the_guard(self):
		event = make_event(self.envelope)
		event.actor = "someone@example.com"
		event.flags.ignore_validate = True
		self.assertRaises(ImmutableRecord, event.save)

	def test_records_cannot_be_deleted(self):
		for doc in (make_event(self.envelope), make_capture(self.envelope), make_template_version()):
			with self.subTest(doctype=doc.doctype):
				self.assertRaises(ImmutableRecord, frappe.delete_doc, doc.doctype, doc.name)
				self.assertTrue(frappe.db.exists(doc.doctype, doc.name))

	def test_event_seq_cannot_fork(self):
		make_event(self.envelope, seq=1)
		with self.assertRaises(frappe.UniqueValidationError):
			make_event(self.envelope, seq=1, hash=sha256_hex(b"fork"))

	def test_event_hashes_must_be_sha256(self):
		self.assertRaises(FieldValidationError, make_event, self.envelope, prev_hash="not-a-hash")

	def test_capture_image_must_be_private(self):
		self.assertRaises(FieldValidationError, make_capture, self.envelope, image="/files/sig.png")


class TestEnvelopeLock(IntegrationTestCase):
	def setUp(self):
		self.envelope = make_envelope()

	def test_new_envelope_starts_as_draft(self):
		self.assertEqual(self.envelope.status, "Draft")
		self.assertRaises(InvalidTransition, make_envelope, status="Sent")

	def test_new_envelope_cannot_carry_service_values(self):
		self.assertRaises(ImmutableRecord, make_envelope, original_sha256=sha256_hex(b"pdf"))
		self.assertRaises(ImmutableRecord, make_envelope, sealing_state="Sealed")

	def test_draft_can_be_edited(self):
		self.envelope.title = "Renamed"
		self.envelope.append(
			"recipients", {"role_label": "Company", "full_name": "Second", "email": "b@example.com"}
		)
		self.envelope.save()
		self.assertEqual(len(self.envelope.reload().recipients), 2)

	def test_status_does_not_change_through_save(self):
		self.envelope.status = "Sent"
		self.assertRaises(InvalidTransition, self.envelope.save)

	def test_service_fields_do_not_change_through_save(self):
		self.envelope.original_sha256 = sha256_hex(b"pdf")
		self.assertRaises(ImmutableRecord, self.envelope.save)

	def test_draft_rows_cannot_carry_service_values(self):
		self.envelope.recipients[0].token_hash = sha256_hex(b"token")
		self.assertRaises(ImmutableRecord, self.envelope.save)
		self.envelope.reload()
		self.envelope.fields[0].filled_on = now_datetime()
		self.assertRaises(ImmutableRecord, self.envelope.save)

	def test_envelope_past_draft_rejects_save(self):
		self.envelope.db_set("status", "Sent")
		self.envelope.reload()
		self.envelope.title = "Changed after send"
		self.assertRaises(ImmutableRecord, self.envelope.save)

		self.envelope.reload()
		self.envelope.title = "Changed with ignore_validate"
		self.envelope.flags.ignore_validate = True
		self.assertRaises(ImmutableRecord, self.envelope.save)

	def test_envelope_being_sent_rejects_save(self):
		self.envelope.db_set("send_state", "Queued")
		self.envelope.reload()
		self.envelope.title = "Changed while queued"
		self.assertRaises(ImmutableRecord, self.envelope.save)

	def test_failed_send_can_be_edited_again(self):
		self.envelope.db_set({"send_state": "Failed", "send_error": "Anchor not found"})
		self.envelope.reload()
		self.envelope.title = "Fixed"
		self.envelope.save()

	def test_services_change_envelopes_with_db_set(self):
		self.envelope.db_set({"status": "In Progress", "sealing_state": "Queued"})
		self.assertEqual(
			frappe.db.get_value("Sign Envelope", self.envelope.name, ["status", "sealing_state"]),
			("In Progress", "Queued"),
		)

	def test_only_drafts_can_be_deleted(self):
		self.envelope.db_set("status", "Voided")
		self.assertRaises(ImmutableRecord, frappe.delete_doc, "Sign Envelope", self.envelope.name)
		draft = make_envelope()
		frappe.delete_doc("Sign Envelope", draft.name)
		self.assertFalse(frappe.db.exists("Sign Envelope", draft.name))

	def test_delegation_inserts_rows_directly_into_a_sent_envelope(self):
		self.envelope.db_set("status", "Sent")
		original = self.envelope.recipients[0]
		delegate = frappe.get_doc(
			{
				"doctype": "Sign Envelope Recipient",
				"parent": self.envelope.name,
				"parenttype": "Sign Envelope",
				"parentfield": "recipients",
				"idx": 2,
				"role_label": original.role_label,
				"full_name": "Delegate",
				"email": "delegate@example.com",
				"status": "Sent",
				"token_hash": sha256_hex(b"delegate-token"),
			}
		).insert()
		field = self.envelope.fields[0]
		field.db_set("recipient_row", delegate.name)
		original.db_set({"status": "Delegated", "delegated_to": delegate.name})

		envelope = frappe.get_doc("Sign Envelope", self.envelope.name)
		self.assertEqual([r.full_name for r in envelope.recipients], ["Test Signer", "Delegate"])
		self.assertEqual(envelope.fields[0].recipient_row, delegate.name)

	def test_field_rects_are_checked(self):
		self.assertRaises(FieldValidationError, make_envelope, fields=[signature_field(x=0.9, w=0.3)])


class TestHashedSecrets(IntegrationTestCase):
	def setUp(self):
		self.envelope = make_envelope()

	def make_session(self, **values):
		return frappe.get_doc(
			{
				"doctype": "Sign Session",
				"envelope": self.envelope.name,
				"recipient_row": self.envelope.recipients[0].name,
				**values,
			}
		).insert()

	def test_session_secret_and_otp_are_stored_hashed(self):
		session = self.make_session(session_hash=sha256_hex(b"secret"), otp_hash=sha256_hex(b"123456"))
		self.assertEqual(len(session.session_hash), 64)
		self.assertRaises(FieldValidationError, self.make_session, session_hash="raw-secret")
		self.assertRaises(FieldValidationError, self.make_session, otp_hash="123456")

	def test_raw_secret_is_rejected_on_update(self):
		session = self.make_session()
		session.otp_hash = "654321"
		session.flags.ignore_validate = True
		self.assertRaises(FieldValidationError, session.save)

	def test_recipient_token_is_stored_hashed(self):
		self.envelope.db_set("status", "Sent")
		row = frappe.get_doc(
			{
				"doctype": "Sign Envelope Recipient",
				"parent": self.envelope.name,
				"parenttype": "Sign Envelope",
				"parentfield": "recipients",
				"full_name": "Raw Token",
				"token_hash": "plain-token-value",
			}
		)
		self.assertRaises(FieldValidationError, row.insert)
