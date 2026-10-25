"""services/envelope.py (P1.8): draft, send, render, void, remind, resend, expire."""

import json
from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from frappe_sign.exceptions import FieldValidationError, ImmutableRecord, InvalidTransition
from frappe_sign.jobs import render as render_job
from frappe_sign.services import audit
from frappe_sign.services import envelope as envelope_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf, make_private_file
from frappe_sign.tests.signing_helpers import (
	COMPANY,
	CUSTOMER,
	capture_tokens,
	make_draft,
	publish_template,
	recipients_by_role,
	send_now,
)
from frappe_sign.utils.files import read_file
from frappe_sign.utils.hashing import sha256_hex


def events_of(name: str) -> list[str]:
	return frappe.get_all("Sign Event", filters={"envelope": name}, pluck="event", order_by="seq asc")


class TestDraft(SignTestCase):
	def test_draft_from_a_template_version(self):
		version = publish_template(otp_mode="Email")
		draft = make_draft(version)
		self.assertEqual((draft.status, draft.template_version, draft.otp_mode), ("Draft", version, "Email"))
		self.assertEqual([r.role_label for r in draft.recipients], ["Customer", "Company"])
		self.assertEqual([r.routing_order for r in draft.recipients], [1, 2])
		self.assertEqual(len(draft.fields), 4)
		self.assertEqual(events_of(draft.name), ["Created"])

	def test_fixed_user_role_fills_itself(self):
		roles = [
			{"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send", "routing_order": 1},
			{
				"role_label": "Company",
				"kind": "Approver",
				"signer_source": "Fixed User",
				"fixed_user": "Administrator",
				"routing_order": 2,
			},
		]
		fields = [
			{
				"field_key": "sig",
				"role_label": "Customer",
				"field_type": "Signature",
				"page": 1,
				"x": 0.1,
				"y": 0.1,
				"w": 0.2,
				"h": 0.05,
			}
		]
		draft = make_draft(publish_template(roles=roles, fields=fields), recipients=[CUSTOMER])
		company = recipients_by_role(draft.name)["Company"]
		self.assertEqual(company.email, frappe.db.get_value("User", "Administrator", "email"))
		self.assertEqual(company.kind, "Approver")

	def test_draft_from_an_uploaded_pdf(self):
		file = make_private_file("upload.pdf", fixture_pdf())
		draft = envelope_service.create_draft(
			{
				"title": "Ad hoc",
				"source_file": file.file_url,
				"signing_order": "Parallel",
				"recipients": [CUSTOMER],
				"fields": [
					{
						"field_key": "s",
						"role_label": "Customer",
						"field_type": "Signature",
						"page": 1,
						"x": 0.1,
						"y": 0.1,
						"w": 0.2,
						"h": 0.05,
					}
				],
			}
		)
		with capture_tokens():
			send_now(draft.name)
		self.assertEqual(frappe.db.get_value("Sign Envelope", draft.name, "status"), "Sent")


class TestSend(SignTestCase):
	def test_send_queues_the_render_job_and_stays_draft(self):
		draft = make_draft()
		with self.capture_enqueue() as calls:
			envelope_service.send(draft.name)
		self.assertEqual(len(calls), 1)
		call = calls[0]
		self.assertEqual(call["method"], "frappe_sign.jobs.render.run")
		self.assertEqual(
			(call["envelope"], call["enqueue_after_commit"], call["deduplicate"]), (draft.name, True, True)
		)
		self.assertEqual(call["job_id"], f"frappe_sign::render::{draft.name}")
		draft.reload()
		self.assertEqual((draft.status, draft.send_state), ("Draft", "Queued"))

	def test_queued_draft_is_locked(self):
		draft = make_draft()
		with self.capture_enqueue():
			envelope_service.send(draft.name)
			self.assertRaises(InvalidTransition, envelope_service.send, draft.name)
		draft.reload()
		draft.title = "Edited while sending"
		self.assertRaises(ImmutableRecord, draft.save)

	def test_send_checks_recipients_and_fields(self):
		cases = {
			"missing email": [CUSTOMER, {**COMPANY, "email": ""}],
			"missing role": [CUSTOMER],
		}
		for label, recipients in cases.items():
			with self.subTest(label):
				draft = make_draft(recipients=recipients)
				with self.capture_enqueue():
					self.assertRaises(FieldValidationError, envelope_service.send, draft.name)

	def test_render_freezes_the_pdf_and_invites_the_first_signer(self):
		draft = make_draft()
		with capture_tokens() as box:
			send_now(draft.name)
		doc = frappe.get_doc("Sign Envelope", draft.name)
		self.assertEqual((doc.status, doc.send_state), ("Sent", "Not Started"))
		pdf = read_file(doc.original_file)
		self.assertEqual(doc.original_sha256, sha256_hex(pdf))
		file = frappe.get_doc("File", doc.original_file)
		self.assertEqual((file.is_private, file.attached_to_name), (1, doc.name))
		self.assertEqual(json.loads(doc.page_metrics)[0]["page"], 1)
		self.assertGreater(doc.expires_on, add_days(now_datetime(), 13))
		roles = recipients_by_role(doc.name)
		self.assertEqual((roles["Customer"].status, roles["Company"].status), ("Sent", "Pending"))
		self.assertEqual(roles["Customer"].token_hash, sha256_hex(box[roles["Customer"].name]))
		self.assertFalse(roles["Company"].token_hash)
		self.assertEqual(
			{f.recipient_row for f in doc.fields if f.role_label == "Customer"}, {roles["Customer"].name}
		)
		self.assertEqual(events_of(doc.name), ["Created", "Sent", "Delivered"])
		self.assertTrue(audit.verify_chain(doc.name).ok)
		queued = frappe.get_all("Email Queue", filters={"reference_name": doc.name}, pluck="name")
		self.assertTrue(queued)

	def test_parallel_invites_every_signer(self):
		draft = make_draft(publish_template(signing_order="Parallel"))
		with capture_tokens() as box:
			send_now(draft.name)
		roles = recipients_by_role(draft.name)
		self.assertEqual({row.status for row in roles.values()}, {"Sent"})
		self.assertEqual(len(box.tokens), 2)

	def test_render_failure_keeps_the_draft(self):
		file = make_private_file("long.pdf", fixture_pdf("many_pages_150.pdf"))
		draft = envelope_service.create_draft(
			{"title": "Long", "source_file": file.file_url, "recipients": [CUSTOMER]}
		)
		frappe.db.set_single_value("Sign Settings", "max_pages", 100)
		with self.capture_enqueue():
			envelope_service.send(draft.name)
		with patch.object(frappe.db, "commit"), patch.object(frappe.db, "rollback"):
			render_job.run(draft.name)
		draft.reload()
		self.assertEqual((draft.status, draft.send_state), ("Draft", "Failed"))
		self.assertIn("too many pages", draft.send_error)
		with self.capture_enqueue() as calls:
			envelope_service.send(draft.name)
		self.assertEqual(len(calls), 1)

	def test_render_job_ignores_an_envelope_that_is_not_queued(self):
		self.assertFalse(envelope_service.render_and_send(make_draft().name))


class TestSenderActions(SignTestCase):
	def sent(self, **kwargs):
		draft = make_draft(**kwargs)
		with capture_tokens() as box:
			send_now(draft.name)
		return draft.name, box

	def test_void(self):
		name, _ = self.sent()
		with self.capture_enqueue() as calls:
			self.assertRaises(FieldValidationError, envelope_service.void, name, " ")
			envelope_service.void(name, "Wrong price")
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertEqual((doc.status, doc.void_reason), ("Voided", "Wrong price"))
		self.assertEqual(events_of(name)[-1], "Voided")
		self.assertIn("envelope_voided", [call.get("event") for call in calls])
		self.assertRaises(InvalidTransition, envelope_service.void, name, "again")

	def test_void_needs_an_open_envelope(self):
		self.assertRaises(InvalidTransition, envelope_service.void, make_draft().name, "x")

	def test_remind_rotates_the_waiting_signer_token(self):
		name, _box = self.sent()
		customer = recipients_by_role(name)["Customer"]
		old = customer.token_hash
		with capture_tokens() as reminder_box:
			self.assertEqual(envelope_service.remind(name), 1)
		customer = recipients_by_role(name)["Customer"]
		self.assertNotEqual(customer.token_hash, old)
		self.assertEqual(customer.token_hash, sha256_hex(reminder_box[customer.name]))
		self.assertTrue(reminder_box.sent[0][2], "sent as a reminder")
		self.assertEqual(events_of(name)[-1], "Reminded")

	def test_resend_to_a_corrected_email(self):
		name, _ = self.sent()
		customer = recipients_by_role(name)["Customer"]
		with capture_tokens() as box:
			envelope_service.resend(name, customer.name, "ahmed.new@example.com")
		customer = recipients_by_role(name)["Customer"]
		self.assertEqual(customer.email, "ahmed.new@example.com")
		self.assertEqual(box.sent[0][1], "ahmed.new@example.com")
		payload = json.loads(
			frappe.get_all(
				"Sign Event", filters={"envelope": name}, fields=["payload"], order_by="seq desc", limit=1
			)[0].payload
		)
		self.assertEqual(payload["previous_email"], "ahmed@example.com")
		company = recipients_by_role(name)["Company"]
		self.assertRaises(InvalidTransition, envelope_service.resend, name, company.name)

	def test_expire(self):
		name, _ = self.sent()
		self.assertFalse(envelope_service.expire(name))
		frappe.db.set_value("Sign Envelope", name, "expires_on", add_days(now_datetime(), -1))
		self.assertEqual(envelope_service.expire_due(), [name])
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "status"), "Expired")
		self.assertEqual(events_of(name)[-1], "Expired")

	def test_transition_guard(self):
		name, _ = self.sent()
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertRaises(InvalidTransition, envelope_service.transition, doc, "Completed")
		self.assertRaises(InvalidTransition, envelope_service.transition, doc, "Draft")
