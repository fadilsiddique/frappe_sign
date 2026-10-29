"""SPA shells at /sign and /s/<token> (P0.5)."""

from pathlib import Path

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.path_resolver import resolve_path
from frappe.website.serve import get_response

from frappe_sign.tests.factories import test_company
from frappe_sign.utils.users import run_as
from frappe_sign.www import s as guest_page
from frappe_sign.www import sign as staff_page

WWW = Path(staff_page.__file__).parent


def make_user(email: str, roles: list[str]) -> str:
	user = frappe.get_doc(
		{"doctype": "User", "email": email, "first_name": "Sign Test", "send_welcome_email": 0}
	).insert()
	user.add_roles(*roles)
	return user.name


class TestShellContext(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.lang = "en"

	def test_guest_is_sent_to_login(self):
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect) as raised:
			staff_page.get_context(frappe._dict())
		self.assertEqual(raised.exception.http_status_code, 302)
		self.assertTrue(frappe.local.flags.redirect_location.startswith("/login?redirect-to="))

	def test_staff_app_needs_a_sign_role(self):
		no_role = make_user("no-sign-role@example.com", [])
		sign_user = make_user("sign-user@example.com", ["Sign User"])
		frappe.set_user(no_role)
		self.assertRaises(frappe.PermissionError, staff_page.get_context, frappe._dict())

		frappe.set_user(sign_user)
		context = frappe._dict()
		staff_page.get_context(context)
		self.assertEqual(context.boot["frappe_sign"]["user"], "sign-user@example.com")
		self.assertEqual(context.boot["frappe_sign"]["full_name"], "Sign Test")

	def test_staff_boot(self):
		context = frappe._dict()
		staff_page.get_context(context)
		self.assertTrue(context.boot["csrf_token"])
		self.assertEqual(
			set(context.boot["frappe_sign"]),
			{
				"user",
				"full_name",
				"user_image",
				"can_manage",
				"whatsapp",
				"lang",
				"dir",
				"branding",
				"messages",
				"languages",
			},
		)
		self.assertTrue(context.boot["frappe_sign"]["can_manage"])
		self.assertEqual(context.boot["frappe_sign"]["dir"], "ltr")
		self.assertEqual(context.boot["frappe_sign"]["full_name"], "Administrator")

	def test_a_sign_user_cannot_manage(self):
		make_user("boot-sign-user@example.com", ["Sign User"])
		with run_as("boot-sign-user@example.com"):
			context = frappe._dict()
			staff_page.get_context(context)
		self.assertFalse(context.boot["frappe_sign"]["can_manage"])

	def test_staff_boot_uses_the_only_profile_branding(self):
		frappe.get_doc(
			{"doctype": "Sign Profile", "company": test_company("Boot Co"), "brand_color": "#0f766e"}
		).insert()
		context = frappe._dict()
		staff_page.get_context(context)
		self.assertEqual(context.boot["frappe_sign"]["branding"]["brand_color"], "#0f766e")

	def test_guest_boot_has_no_csrf_token_or_user(self):
		frappe.set_user("Guest")
		context = frappe._dict()
		guest_page.get_context(context)
		self.assertNotIn("csrf_token", context.boot)
		self.assertIsNone(context.boot["frappe_sign"]["user"])
		self.assertNotIn("full_name", context.boot["frappe_sign"])

	def test_logged_in_signer_gets_a_csrf_token(self):
		context = frappe._dict()
		guest_page.get_context(context)
		self.assertTrue(context.boot["csrf_token"])
		self.assertEqual(context.boot["frappe_sign"]["user"], "Administrator")

	def test_guest_headers(self):
		from werkzeug.wrappers import Response

		from frappe_sign.utils.http import after_request

		for path, expected in (
			("/s/abc", "no-referrer"),
			("/api/method/frappe_sign.api.guest.open", "no-referrer"),
			("/app", None),
		):
			response = Response("x")
			after_request(response=response, request=frappe._dict(path=path))
			self.assertEqual(response.headers.get("Referrer-Policy"), expected, path)

	def test_arabic_is_right_to_left(self):
		frappe.local.lang = "ar"
		context = frappe._dict()
		guest_page.get_context(context)
		self.assertEqual(context.boot["frappe_sign"]["dir"], "rtl")


class TestShellRoutes(IntegrationTestCase):
	def test_deep_links_resolve_to_the_shells(self):
		# Dynamic routes resolve only inside a request.
		for path, endpoint in (("sign/templates/STPL-00001/design", "sign"), ("s/some-token", "s")):
			frappe.utils.set_request(method="GET", path=path)
			self.assertEqual(resolve_path(path), endpoint)

	def test_shells_render(self):
		if not (WWW / "s.html").exists():
			self.skipTest("Frontend not built: run `bench build --app frappe_sign` first.")
		for path, entry in (("s/abc123", "guest-"), ("sign/requests", "staff-")):
			with self.subTest(path=path):
				frappe.set_user("Guest" if path.startswith("s/") else "Administrator")
				frappe.utils.set_request(method="GET", path=path)
				response = get_response(path)
				html = response.get_data(as_text=True)
				self.assertEqual(response.status_code, 200, html[:500])
				self.assertIn('<div id="app"></div>', html)
				self.assertIn(f"/assets/frappe_sign/frontend/assets/{entry}", html)
				self.assertIn('window["frappe_sign"]', html)
		frappe.set_user("Administrator")


class TestVerifyPage(IntegrationTestCase):
	def test_verify_page_renders_for_guests_with_the_envelope_prefilled(self):
		frappe.set_user("Guest")
		try:
			frappe.utils.set_request(
				method="GET", path="sign-verify", query_string="envelope=SIGN-2026-00001"
			)
			response = get_response("sign-verify")
			html = response.get_data(as_text=True)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(response.status_code, 200, html[:300])
		self.assertIn('id="sign-verify-form"', html)
		self.assertIn('value="SIGN-2026-00001"', html)
		self.assertIn("frappe_sign.api.public.verify", html)

	def test_prefill_is_escaped(self):
		frappe.set_user("Guest")
		try:
			frappe.utils.set_request(
				method="GET",
				path="sign-verify",
				query_string="envelope=%22%3E%3Cscript%3Ealert(1)%3C/script%3E",
			)
			html = get_response("sign-verify").get_data(as_text=True)
		finally:
			frappe.set_user("Administrator")
		self.assertNotIn("<script>alert(1)</script>", html)
		self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
