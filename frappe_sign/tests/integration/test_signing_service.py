"""services/signing.py (P1.9): the guest flow, per path."""

import io
import json
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime
from PIL import Image
from pypdf import PdfReader

from frappe_sign.exceptions import (
	EnvelopeNotOpen,
	FieldValidationError,
	InvalidTransition,
	LinkExpired,
	NotYourTurn,
	OtpCooldown,
	OtpInvalid,
	RecipientDone,
	SessionInvalid,
)
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import notify, sealing, signing
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.signing_helpers import (
	CUSTOMER,
	capture_tokens,
	make_draft,
	publish_template,
	recipients_by_role,
	send_now,
)
from frappe_sign.tests.unit.test_overlay import signature_png
from frappe_sign.utils.files import read_file
from frappe_sign.utils.hashing import sha256_hex
from frappe_sign.utils.request import Client

CLIENT = Client(ip="203.0.113.7", user_agent="Mozilla/5.0 (iPhone; test)")


def events_of(name: str) -> list[str]:
	return frappe.get_all("Sign Event", filters={"envelope": name}, pluck="event", order_by="seq asc")


def jpeg() -> bytes:
	out = io.BytesIO()
	Image.new("RGB", (60, 20), (10, 10, 10)).save(out, "JPEG")
	return out.getvalue()


class SigningCase(SignTestCase):
	def sent(self, **template):
		version = publish_template(**template)
		draft = make_draft(version)
		self.box_ctx = capture_tokens()
		self.box = self.box_ctx.__enter__()
		self.addCleanup(self.box_ctx.__exit__, None, None, None)
		send_now(draft.name)
		self.name = draft.name
		return draft.name

	def token(self, role: str) -> str:
		return self.box[recipients_by_role(self.name)[role].name]

	def start(self, role: str = "Customer") -> str:
		result = signing.open(self.token(role), CLIENT)
		signing.consent(result["session"], result["consent"]["version"], CLIENT)
		return result["session"]

	def sign(self, role: str = "Customer", **values) -> dict:
		secret = self.start(role)
		key = "customer_signature" if role == "Customer" else "company_signature"
		signing.save_capture(secret, key, "Draw", signature_png(), client=CLIENT)
		if values:
			signing.save_fields(secret, values, CLIENT)
		with self.capture_enqueue() as self.enqueued:
			return signing.finish(secret, CLIENT)


class TestOpen(SigningCase):
	def test_open_without_otp_gives_a_session_and_a_scoped_summary(self):
		self.sent()
		result = signing.open(self.token("Customer"), CLIENT)
		self.assertTrue(result["session"])
		self.assertFalse(result["otp_required"])
		self.assertEqual(result["recipient"]["email"], "ahmed@example.com")
		self.assertEqual(
			{f["key"] for f in result["fields"]}, {"customer_signature", "customer_name", "customer_date"}
		)
		text = json.dumps(result)
		self.assertNotIn("fatima@example.com", text, "other recipients' emails")
		self.assertNotIn("reference_name", text)
		self.assertNotIn(self.token("Customer"), text)
		customer = recipients_by_role(self.name)["Customer"]
		self.assertEqual(customer.status, "Viewed")
		self.assertEqual(events_of(self.name)[-1], "Viewed")
		session = frappe.get_all(
			"Sign Session", filters={"envelope": self.name}, fields=["session_hash", "ip"]
		)[0]
		self.assertEqual((session.session_hash, session.ip), (sha256_hex(result["session"]), "203.0.113.7"))

	def test_unknown_and_expired_tokens(self):
		self.sent()
		self.assertRaises(LinkExpired, signing.open, "not-a-token", CLIENT)
		self.assertRaises(LinkExpired, signing.open, "", CLIENT)
		customer = recipients_by_role(self.name)["Customer"]
		frappe.db.set_value(
			"Sign Envelope Recipient",
			customer.name,
			"token_expires_on",
			now_datetime() - timedelta(minutes=1),
		)
		self.assertRaises(LinkExpired, signing.open, self.token("Customer"), CLIENT)

	def test_reminders_keep_the_link_and_resend_replaces_it(self):
		self.sent()
		first = self.token("Customer")
		envelope_service.remind(self.name)
		self.assertTrue(
			signing.open(first, CLIENT)["session"], "the first email still works after a reminder"
		)
		envelope_service.resend(self.name, recipients_by_role(self.name)["Customer"].name)
		self.assertRaises(LinkExpired, signing.open, first, CLIENT)
		self.assertTrue(signing.open(self.token("Customer"), CLIENT)["session"])

	def test_sequential_signer_waits_for_their_turn(self):
		self.sent()
		doc = frappe.get_doc("Sign Envelope", self.name)
		envelope_service.invite(doc, recipients_by_role(self.name)["Company"])
		with self.assertRaises(NotYourTurn) as caught:
			signing.open(self.token("Company"), CLIENT)
		self.assertEqual(caught.exception.data["waiting_for"], ["Ahmed Khan"])

	def test_voided_envelope_is_not_open(self):
		self.sent()
		envelope_service.void(self.name, "Cancelled")
		with self.assertRaises(EnvelopeNotOpen) as caught:
			signing.open(self.token("Customer"), CLIENT)
		self.assertEqual(caught.exception.data["status"], "Voided")


class TestOtp(SigningCase):
	def request(self):
		codes = []
		original = notify.send_otp

		def record(envelope, recipient, code, minutes):
			codes.append(code)
			original(envelope, recipient, code, minutes)

		with patch.object(notify, "send_otp", side_effect=record):
			result = signing.request_otp(self.token("Customer"), "Email", CLIENT)
		return codes[-1], result

	def test_email_otp_flow(self):
		self.sent(otp_mode="Email")
		opened = signing.open(self.token("Customer"), CLIENT)
		self.assertTrue(opened["otp_required"])
		self.assertNotIn("session", opened)
		code, result = self.request()
		self.assertEqual(result["sent_to"], "a****@example.com")
		stored = frappe.get_all(
			"Sign Session", filters={"envelope": self.name}, fields=["otp_hash", "verified_on"]
		)[0]
		self.assertEqual(stored.otp_hash, sha256_hex(code))
		self.assertIsNone(stored.verified_on)
		verified = signing.verify_otp(self.token("Customer"), code, CLIENT)
		self.assertTrue(verified["session"])
		self.assertEqual(signing.state(verified["session"])["recipient"]["status"], "Viewed")
		self.assertIn("OTP Verified", events_of(self.name))
		self.assertRaises(OtpInvalid, signing.verify_otp, self.token("Customer"), code, CLIENT)

	def test_resend_cooldown(self):
		self.sent(otp_mode="Email")
		self.request()
		with self.assertRaises(OtpCooldown) as caught:
			self.request()
		self.assertGreater(caught.exception.data["retry_after"], 0)

	def test_five_wrong_codes_lock_the_code(self):
		self.sent(otp_mode="Email")
		code, _ = self.request()
		wrong = "000000" if code != "000000" else "111111"
		for left in (4, 3, 2, 1, 0):
			with self.assertRaises(OtpInvalid) as caught:
				signing.verify_otp(self.token("Customer"), wrong, CLIENT)
			self.assertEqual(caught.exception.data["attempts_left"], left)
		with self.assertRaises(OtpInvalid) as caught:
			signing.verify_otp(self.token("Customer"), code, CLIENT)
		self.assertEqual(caught.exception.data["reason"], "too_many")

	def test_expired_code(self):
		self.sent(otp_mode="Email")
		code, _ = self.request()
		frappe.db.set_value(
			"Sign Session", {"envelope": self.name}, "otp_expires_on", now_datetime() - timedelta(seconds=1)
		)
		with self.assertRaises(OtpInvalid) as caught:
			signing.verify_otp(self.token("Customer"), code, CLIENT)
		self.assertEqual(caught.exception.data["reason"], "expired")

	def test_channel_must_match(self):
		self.sent(otp_mode="Email")
		self.assertRaises(
			FieldValidationError, signing.request_otp, self.token("Customer"), "WhatsApp", CLIENT
		)
		self.sent()
		self.assertRaises(FieldValidationError, signing.request_otp, self.token("Customer"), "Email", CLIENT)


class TestSession(SigningCase):
	def test_invalid_idle_and_expired_sessions(self):
		self.sent()
		self.assertRaises(SessionInvalid, signing.state, "nope")
		self.assertRaises(SessionInvalid, signing.state, None)
		secret = signing.open(self.token("Customer"), CLIENT)["session"]
		session = frappe.db.get_value("Sign Session", {"session_hash": sha256_hex(secret)})
		frappe.db.set_value("Sign Session", session, "last_seen_on", now_datetime() - timedelta(minutes=31))
		self.assertRaises(SessionInvalid, signing.state, secret)
		frappe.db.set_value(
			"Sign Session",
			session,
			{"last_seen_on": now_datetime(), "expires_on": now_datetime() - timedelta(seconds=1)},
		)
		self.assertRaises(SessionInvalid, signing.state, secret)

	def test_using_a_session_keeps_it_alive(self):
		self.sent()
		secret = signing.open(self.token("Customer"), CLIENT)["session"]
		session = frappe.db.get_value("Sign Session", {"session_hash": sha256_hex(secret)})
		frappe.db.set_value("Sign Session", session, "last_seen_on", now_datetime() - timedelta(minutes=29))
		signing.state(secret)
		self.assertLess(
			(now_datetime() - frappe.db.get_value("Sign Session", session, "last_seen_on")).total_seconds(),
			60,
		)


class TestFields(SigningCase):
	def setUp(self):
		super().setUp()
		fields = [
			{
				"field_key": "sig",
				"role_label": "Customer",
				"field_type": "Signature",
				"page": 1,
				"x": 0.1,
				"y": 0.1,
				"w": 0.3,
				"h": 0.05,
			},
			{
				"field_key": "amount",
				"role_label": "Customer",
				"field_type": "Number",
				"page": 1,
				"x": 0.1,
				"y": 0.2,
				"w": 0.3,
				"h": 0.03,
				"required": 0,
			},
			{
				"field_key": "plan",
				"role_label": "Customer",
				"field_type": "Dropdown",
				"options": "Basic\nPro",
				"page": 1,
				"x": 0.1,
				"y": 0.3,
				"w": 0.3,
				"h": 0.03,
				"required": 0,
			},
			{
				"field_key": "code",
				"role_label": "Customer",
				"field_type": "Text",
				"validation_regex": "[A-Z]{3}",
				"page": 1,
				"x": 0.1,
				"y": 0.4,
				"w": 0.3,
				"h": 0.03,
				"required": 0,
			},
			{
				"field_key": "agree",
				"role_label": "Customer",
				"field_type": "Checkbox",
				"page": 1,
				"x": 0.1,
				"y": 0.5,
				"w": 0.03,
				"h": 0.02,
			},
			{
				"field_key": "fixed",
				"role_label": "Customer",
				"field_type": "Text",
				"read_only": 1,
				"page": 1,
				"x": 0.1,
				"y": 0.6,
				"w": 0.3,
				"h": 0.03,
				"required": 0,
			},
			{
				"field_key": "company_sig",
				"role_label": "Company",
				"field_type": "Signature",
				"page": 1,
				"x": 0.5,
				"y": 0.9,
				"w": 0.3,
				"h": 0.05,
			},
		]
		self.sent(fields=fields)
		self.secret = signing.open(self.token("Customer"), CLIENT)["session"]

	def consent(self):
		signing.consent(self.secret, signing.settings.consent()[1], CLIENT)

	def test_consent_comes_first(self):
		self.assertRaises(FieldValidationError, signing.save_fields, self.secret, {"amount": "5"})
		self.assertRaises(FieldValidationError, signing.consent, self.secret, 99)
		self.consent()
		self.assertIn("Consented", events_of(self.name))
		signing.save_fields(self.secret, {"amount": "5"})

	def test_values_are_validated_on_the_server(self):
		self.consent()
		bad = {
			"amount": "five",
			"plan": "Enterprise",
			"code": "abc",
			"company_sig": "x",
			"sig": "typed",
			"fixed": "changed",
			"unknown": "x",
		}
		for key, value in bad.items():
			with self.subTest(key):
				self.assertRaises(FieldValidationError, signing.save_fields, self.secret, {key: value})
		result = signing.save_fields(
			self.secret, {"amount": "1,250.50", "plan": "Pro", "code": "ABC", "agree": True}
		)
		values = {f["key"]: f["value"] for f in result["fields"]}
		self.assertEqual(
			(values["amount"], values["plan"], values["code"], values["agree"]),
			("1,250.50", "Pro", "ABC", "1"),
		)
		self.assertEqual(events_of(self.name)[-1], "Field Filled")

	def test_captures_are_checked_and_stored_privately(self):
		self.consent()
		self.assertRaises(FieldValidationError, signing.save_capture, self.secret, "sig", "Draw", b"<svg/>")
		self.assertRaises(
			FieldValidationError, signing.save_capture, self.secret, "sig", "Scribble", signature_png()
		)
		self.assertRaises(
			FieldValidationError, signing.save_capture, self.secret, "company_sig", "Draw", signature_png()
		)
		self.assertRaises(
			FieldValidationError, signing.save_capture, self.secret, "amount", "Draw", signature_png()
		)
		signing.save_capture(self.secret, "sig", "Upload", jpeg())
		field = next(f for f in frappe.get_doc("Sign Envelope", self.name).fields if f.field_key == "sig")
		capture = frappe.get_doc("Sign Capture", field.capture)
		self.assertTrue(capture.image.startswith("/private/files/"))
		self.assertEqual(capture.method, "Upload")
		stored = read_file(frappe.db.get_value("File", {"file_url": capture.image}))
		self.assertEqual(capture.sha256, sha256_hex(stored))
		self.assertTrue(stored.startswith(b"\x89PNG"), "re-encoded as PNG")

	def test_finish_needs_required_fields(self):
		self.consent()
		with self.assertRaises(FieldValidationError) as caught:
			signing.finish(self.secret, CLIENT)
		self.assertEqual(set(caught.exception.data["missing"]), {"sig", "agree"})


class TestFinish(SigningCase):
	def test_sequential_flow_renders_intermediates_and_queues_one_seal(self):
		self.sent()
		result = self.sign("Customer")
		self.assertEqual(result, {"status": "Signed", "completed": False})
		doc = frappe.get_doc("Sign Envelope", self.name)
		customer, company = (
			recipients_by_role(self.name)["Customer"],
			recipients_by_role(self.name)["Company"],
		)
		self.assertEqual((doc.status, customer.status, company.status), ("In Progress", "Signed", "Sent"))
		first_pdf = read_file(customer.intermediate_file)
		self.assertEqual(customer.intermediate_sha256, sha256_hex(first_pdf))
		text = PdfReader(io.BytesIO(first_pdf)).pages[0].extract_text()
		self.assertIn("Ahmed Khan", text, "Full Name fills itself")
		values = {f.field_key: f.value for f in doc.fields}
		self.assertEqual(values["customer_date"], frappe.utils.formatdate(frappe.utils.today()))
		payload = json.loads(
			frappe.get_all("Sign Event", filters={"envelope": self.name, "event": "Signed"}, pluck="payload")[
				0
			]
		)
		self.assertEqual(payload, {"intermediate_sha256": customer.intermediate_sha256, "kind": "Signer"})
		self.assertEqual(
			[c.get("event") for c in self.enqueued if c["method"].endswith("events.run")][-1],
			"recipient_signed",
		)

		pdf, _name = signing.get_pdf(signing.open(self.token("Company"), CLIENT)["session"])
		self.assertEqual(pdf, first_pdf, "the next signer sees the first signer's intermediate PDF")
		result = self.sign("Company")
		self.assertEqual(result, {"status": "Signed", "completed": True})
		doc.reload()
		self.assertEqual((doc.status, doc.sealing_state), ("In Progress", "Queued"))
		seal_jobs = [c for c in self.enqueued if c["method"] == sealing.JOB]
		self.assertEqual(len(seal_jobs), 1)
		self.assertEqual(
			(
				seal_jobs[0]["job_id"],
				seal_jobs[0]["deduplicate"],
				seal_jobs[0]["enqueue_after_commit"],
				seal_jobs[0]["queue"],
			),
			(f"frappe_sign::seal::{self.name}", True, True, "long"),
		)
		company = recipients_by_role(self.name)["Company"]
		self.assertNotEqual(company.intermediate_sha256, customer.intermediate_sha256)

	def test_parallel_signers_can_sign_in_any_order(self):
		self.sent(signing_order="Parallel")
		self.sign("Company")
		result = self.sign("Customer")
		self.assertTrue(result["completed"])

	def test_signed_recipient_cannot_act_again(self):
		self.sent()
		self.sign("Customer")
		with self.assertRaises(RecipientDone) as caught:
			signing.open(self.token("Customer"), CLIENT)
		self.assertEqual(caught.exception.data["status"], "Signed")

	def test_approver_approves_by_finishing(self):
		roles = [
			{"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send", "routing_order": 1},
			{"role_label": "Manager", "kind": "Approver", "signer_source": "Ask at Send", "routing_order": 2},
		]
		fields = [
			{
				"field_key": "customer_signature",
				"role_label": "Customer",
				"field_type": "Signature",
				"page": 1,
				"x": 0.1,
				"y": 0.1,
				"w": 0.3,
				"h": 0.05,
			}
		]
		version = publish_template(roles=roles, fields=fields)
		draft = make_draft(
			version,
			recipients=[
				CUSTOMER,
				{"role_label": "Manager", "full_name": "Omar", "email": "omar@example.com"},
			],
		)
		with capture_tokens() as box:
			send_now(draft.name)
			self.name, self.box = draft.name, box
			self.sign("Customer")
			secret = self.start("Manager")
			self.assertEqual(signing.state(secret)["fields"], [])
			with self.capture_enqueue():
				result = signing.finish(secret, CLIENT)
		self.assertTrue(result["completed"])
		payloads = [
			json.loads(p)
			for p in frappe.get_all(
				"Sign Event",
				filters={"envelope": draft.name, "event": "Signed"},
				pluck="payload",
				order_by="seq asc",
			)
		]
		self.assertEqual(payloads[-1]["kind"], "Approver")


class TestDeclineAndDelegate(SigningCase):
	def test_decline_ends_the_envelope(self):
		self.sent()
		secret = self.start()
		self.assertRaises(FieldValidationError, signing.decline, secret, "  ")
		with self.capture_enqueue() as calls:
			signing.decline(secret, "Price is wrong")
		doc = frappe.get_doc("Sign Envelope", self.name)
		customer = recipients_by_role(self.name)["Customer"]
		self.assertEqual(
			(doc.status, customer.status, customer.decline_reason), ("Declined", "Declined", "Price is wrong")
		)
		self.assertIn("envelope_declined", [c.get("event") for c in calls])
		self.assertRaises(SessionInvalid, signing.state, secret)
		self.assertRaises(EnvelopeNotOpen, signing.open, self.token("Customer"), CLIENT)

	def test_delegate_moves_fields_to_the_new_signer(self):
		self.sent()
		secret = self.start()
		self.assertRaises(FieldValidationError, signing.delegate, secret, "Sara", "ahmed@example.com")
		signing.delegate(secret, "Sara Saleh", "Sara@Example.com")
		rows = frappe.get_doc("Sign Envelope", self.name).recipients
		old = next(r for r in rows if r.email == "ahmed@example.com")
		new = next(r for r in rows if r.email == "sara@example.com")
		self.assertEqual(
			(old.status, old.delegated_to, new.status, new.role_label),
			("Delegated", new.name, "Sent", "Customer"),
		)
		fields = {f.field_key: f.recipient_row for f in frappe.get_doc("Sign Envelope", self.name).fields}
		self.assertEqual(fields["customer_signature"], new.name)
		self.assertIn(new.name, self.box.tokens)
		self.assertRaises(SessionInvalid, signing.state, secret)
		self.assertEqual(events_of(self.name)[-2:], ["Delegated", "Delivered"])
		result = signing.open(self.box[new.name], CLIENT)
		self.assertIn("customer_signature", {f["key"] for f in result["fields"]})

	def test_delegation_must_be_allowed_by_the_role(self):
		self.sent(signing_order="Parallel")
		secret = self.start("Company")
		self.assertRaises(InvalidTransition, signing.delegate, secret, "Sara", "sara@example.com")
