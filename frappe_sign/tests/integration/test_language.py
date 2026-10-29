"""Arabic and RTL plumbing (P3.5): boot messages, envelope language, Arabic emails, guest page language."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from frappe_sign.services import notify
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_user
from frappe_sign.tests.signing_helpers import make_draft, publish_template
from frappe_sign.utils import boot
from frappe_sign.utils.languages import is_arabic, shipped_language
from frappe_sign.www import s as guest_page

CONTEXT = {
	"sender_name": "Layla",
	"envelope_title": "Service Agreement",
	"recipient_name": "Ahmed",
	"link": "https://x/s/t",
	"expires_on": "2026-11-01",
	"brand_color": "#111827",
	"button_text_color": "#ffffff",
	"message": "",
}


class TestLanguages(UnitTestCase):
	def test_arabic_variants_map_to_ar_and_the_rest_to_en(self):
		self.assertTrue(is_arabic("ar"))
		self.assertTrue(is_arabic("ar-SA"))
		self.assertFalse(is_arabic("en"))
		self.assertEqual(
			[shipped_language(x) for x in ("ar-AE", "de", None, "en-GB")], ["ar", "en", "en", "en"]
		)


class TestBoot(SignTestCase):
	def test_arabic_boot_has_direction_and_messages(self):
		with patch.object(frappe.local, "lang", "ar"):
			result = boot.base_boot("a@example.com")
		self.assertEqual((result["lang"], result["dir"]), ("ar", "rtl"))
		self.assertEqual(result["messages"]["Signature request"], "طلب توقيع")
		self.assertEqual(result["languages"], ["en", "ar"])

	def test_english_boot_has_no_messages(self):
		with patch.object(frappe.local, "lang", "en"):
			result = boot.base_boot(None)
		self.assertEqual((result["dir"], result["messages"]), ("ltr", {}))


class TestEnvelopeLanguage(SignTestCase):
	def test_defaults_to_the_senders_language_and_can_be_chosen(self):
		make_user("arabic-sender@example.com", "Sign User")
		frappe.db.set_value("User", "arabic-sender@example.com", "language", "ar")
		version = publish_template()
		with self.as_user("arabic-sender@example.com"):
			self.assertEqual(make_draft(version).language, "ar")
			self.assertEqual(make_draft(version, language="en").language, "en")
		self.assertEqual(
			make_draft(language="de").language, "en", "unsupported languages fall back to English"
		)


class TestArabicEmail(SignTestCase):
	def test_built_in_templates_have_an_arabic_version(self):
		for name in (
			notify.INVITATION,
			notify.REMINDER,
			notify.OTP,
			notify.COMPLETED,
			notify.DECLINED,
			notify.VOIDED,
			notify.FAILED,
		):
			subject, body = notify.render(
				name,
				CONTEXT
				| {"otp": "123456", "minutes": 10, "reason": "x", "declined_by": "A", "envelope": "SIGN-1"},
				"ar",
			)
			self.assertRegex(subject + body, r"[؀-ۿ]", name)
			self.assertIn('dir="rtl"', body, name)

	def test_english_stays_english(self):
		subject, body = notify.render(notify.INVITATION, CONTEXT, "en")
		self.assertEqual(subject, "Layla sent you Service Agreement to sign")
		self.assertNotIn("dir=", body)

	def test_the_shell_flips_in_arabic(self):
		envelope = SimpleNamespace(company=None)
		with patch.object(
			notify, "profile_branding", return_value={"company": "Gulf", "logo": None, "brand_color": None}
		):
			with notify.print_language("ar"):
				html = notify.wrap("<p>x</p>", envelope)
			ltr = notify.wrap("<p>x</p>", envelope)
		self.assertIn('dir="rtl"', html)
		self.assertIn("text-align:right", html)
		self.assertIn("أُرسل بواسطة Frappe Sign", html)
		self.assertIn('dir="ltr"', ltr)

	def test_custom_templates_are_not_swapped(self):
		with patch.object(frappe.db, "exists", return_value=False):
			subject, _ = notify.render("My Own Template", CONTEXT, "ar")
		self.assertEqual(
			subject, "Layla sent you Service Agreement to sign", "unknown names use the invitation fallback"
		)


class TestGuestPageLanguage(SignTestCase):
	def test_the_envelope_language_applies_unless_the_signer_chose_one(self):
		with (
			patch.object(frappe.local, "lang", "en"),
			patch.object(guest_page, "request_cookie", return_value=None),
		):
			guest_page.use_language("ar")
			self.assertEqual(frappe.local.lang, "ar")
		with (
			patch.object(frappe.local, "lang", "en"),
			patch.object(guest_page, "request_cookie", return_value="en"),
		):
			guest_page.use_language("ar")
			self.assertEqual(frappe.local.lang, "en")
		with patch.object(frappe.local, "lang", "en"):
			guest_page.use_language(None)
			self.assertEqual(frappe.local.lang, "en")
