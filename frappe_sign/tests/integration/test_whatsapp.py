"""services/whatsapp.py (P3.1): WhatsApp OTP and invitations, with frappe_whatsapp absent or present."""

import json
import re
from unittest.mock import MagicMock, patch

import frappe

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import notify, signing, whatsapp
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.integration.test_signing_service import CLIENT, SigningCase
from frappe_sign.tests.signing_helpers import COMPANY, CUSTOMER, make_draft, publish_template
from frappe_sign.utils.hashing import sha256_hex

MOBILE = "+971500000001"
CUSTOMER_WITH_MOBILE = CUSTOMER | {"mobile": MOBILE}


def fake_whatsapp(enabled: bool = True):
	"""Pretend frappe_whatsapp is installed; return the list of messages it was asked to send."""
	sent: list[dict] = []

	def message(to, text, envelope):
		doc = MagicMock()
		doc.insert.side_effect = lambda **kwargs: sent.append({"to": to, "text": text, "envelope": envelope})
		return doc

	patches = [
		patch.object(whatsapp, "available", return_value=True),
		patch.object(whatsapp, "enabled", return_value=enabled),
		patch.object(whatsapp, "message", side_effect=message),
	]
	return sent, patches


class TestWithoutWhatsapp(SignTestCase):
	def test_not_available_without_the_app(self):
		with patch("frappe_sign.services.whatsapp.app_installed", return_value=False):
			self.assertFalse(whatsapp.available())
			self.assertFalse(whatsapp.any_enabled())

	def test_send_refuses_whatsapp_otp(self):
		version = publish_template(otp_mode="WhatsApp")
		draft = make_draft(version, recipients=[CUSTOMER_WITH_MOBILE])
		with patch.object(whatsapp, "enabled", return_value=False):
			self.assertRaises(FieldValidationError, envelope_service.check_sendable, draft)


class TestMobile(SignTestCase):
	def test_mask_mobile(self):
		self.assertEqual(whatsapp.mask_mobile("+971 50 000 0001"), "*********001")
		self.assertEqual(whatsapp.mask_mobile(""), "")


class TestWhatsappOtp(SigningCase):
	def start_whatsapp(self, recipients):
		self.messages, patches = fake_whatsapp()
		for p in patches:
			p.start()
			self.addCleanup(p.stop)
		self.sent(recipients=recipients, otp_mode="WhatsApp")

	def test_otp_goes_to_the_mobile_and_verifies(self):
		self.start_whatsapp([CUSTOMER_WITH_MOBILE, COMPANY | {"mobile": "+971500000002"}])
		result = signing.request_otp(self.token("Customer"), "WhatsApp", CLIENT)
		self.assertEqual(result["sent_to"], whatsapp.mask_mobile(MOBILE))
		self.assertEqual(self.messages[-1]["to"], MOBILE)
		code = re.search(r"\b(\d{6})\b", self.messages[-1]["text"]).group(1)
		stored = frappe.get_all("Sign Session", filters={"envelope": self.name}, fields=["otp_hash"])[0]
		self.assertEqual(stored.otp_hash, sha256_hex(code))
		self.assertTrue(signing.verify_otp(self.token("Customer"), code, CLIENT)["session"])
		payloads = frappe.get_all(
			"Sign Event", filters={"envelope": self.name, "event": "OTP Sent"}, pluck="payload"
		)
		self.assertEqual(json.loads(payloads[0])["channel"], "whatsapp")

	def test_a_signer_without_a_mobile_cannot_be_sent(self):
		_sent, patches = fake_whatsapp()
		for p in patches:
			p.start()
			self.addCleanup(p.stop)
		draft = make_draft(publish_template(otp_mode="WhatsApp"), recipients=[CUSTOMER, COMPANY])
		self.assertRaises(FieldValidationError, envelope_service.check_sendable, draft)


class TestWhatsappInvitation(SignTestCase):
	def test_invitation_follows_email_when_enabled(self):
		sent, patches = fake_whatsapp()
		for p in patches:
			p.start()
			self.addCleanup(p.stop)
		draft = make_draft(recipients=[CUSTOMER_WITH_MOBILE])
		recipient = draft.recipients[0]
		self.assertTrue(notify.try_send_invitation(draft, recipient, "tok"))
		self.assertEqual(sent[0]["to"], MOBILE)
		self.assertIn("/s/tok", sent[0]["text"])

	def test_no_message_when_disabled_or_no_mobile(self):
		sent, patches = fake_whatsapp(enabled=False)
		for p in patches:
			p.start()
			self.addCleanup(p.stop)
		draft = make_draft(recipients=[CUSTOMER_WITH_MOBILE])
		notify.try_send_invitation(draft, draft.recipients[0], "tok")
		self.assertEqual(sent, [])

	def test_a_failed_message_is_logged_and_does_not_fail_the_email(self):
		_sent, patches = fake_whatsapp()
		for p in patches:
			p.start()
			self.addCleanup(p.stop)
		draft = make_draft(recipients=[CUSTOMER_WITH_MOBILE])
		with patch.object(whatsapp, "send_text", side_effect=frappe.ValidationError("no account")):
			self.assertTrue(notify.try_send_invitation(draft, draft.recipients[0], "tok"))
		self.assertTrue(
			frappe.db.exists("Error Log", {"method": ["like", "Frappe Sign: whatsapp%"]})
			or frappe.db.exists("Error Log", {"reference_name": draft.name})
		)
