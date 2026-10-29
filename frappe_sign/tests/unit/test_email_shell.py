"""Branded email shell (U.11): logo, company name, brand color button, escaping."""

from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from frappe_sign.services import notify

BRANDING = {"company": "Gulf Trading LLC", "logo": "/files/logo.png", "brand_color": "#0f766e"}


class TestEmailShell(UnitTestCase):
	def wrap(self, branding, body="<p>Hello</p>"):
		with patch.object(notify, "profile_branding", return_value=branding):
			return notify.wrap(body, SimpleNamespace(company="Gulf Trading LLC"))

	def test_shell_shows_the_logo_name_body_and_footer(self):
		html = self.wrap(BRANDING)
		self.assertIn("/files/logo.png", html)
		self.assertIn("Gulf Trading LLC", html)
		self.assertIn("<p>Hello</p>", html)
		self.assertIn("Sent with Frappe Sign", html)

	def test_shell_without_a_profile_still_wraps_the_body(self):
		html = self.wrap({"company": None, "logo": None, "brand_color": None})
		self.assertIn("<p>Hello</p>", html)
		self.assertNotIn("<img", html)

	def test_company_name_is_escaped(self):
		html = self.wrap(BRANDING | {"company": "<b>X</b>"})
		self.assertNotIn("<b>X</b>", html)

	def test_button_text_contrasts_with_the_brand_color(self):
		self.assertEqual(notify.contrast_color("#0f766e"), "#ffffff")
		self.assertEqual(notify.contrast_color("#fde047"), "#111827")

	def test_invalid_brand_color_falls_back_to_the_default(self):
		with patch.object(notify, "profile_branding", return_value={"brand_color": "red; x"}):
			self.assertEqual(notify.brand_color(SimpleNamespace(company="A")), notify.DEFAULT_BRAND)

	def test_invitation_button_uses_the_brand_color(self):
		context = {
			"brand_color": "#0f766e",
			"button_text_color": "#ffffff",
			"link": "https://x/s/t",
			"expires_on": "1 Jan",
		}
		_, message = notify.render("Frappe Sign Invitation", context)
		self.assertIn("background:#0f766e", message)
		self.assertIn('href="https://x/s/t"', message)
