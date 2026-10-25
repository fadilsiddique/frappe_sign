"""Guest API security (P1.12, DESIGN 5.2 and 9): rate limits, scoping, token rotation, sessions."""

import ast
import base64
import inspect
import random
from pathlib import Path

import frappe
from frappe.utils import set_request

from frappe_sign.api import guest
from frappe_sign.exceptions import FrappeSignError
from frappe_sign.services import envelope as envelope_service
from frappe_sign.tests.integration.test_signing_service import SigningCase
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, recipients_by_role, send_now
from frappe_sign.tests.unit.test_overlay import signature_png
from frappe_sign.utils.files import read_file
from frappe_sign.utils.hashing import sha256_hex


def random_ip() -> str:
	return f"198.18.{random.randint(0, 255)}.{random.randint(1, 254)}"


class GuestApiCase(SigningCase):
	def setUp(self):
		super().setUp()
		self.ip = random_ip()

	def call(self, endpoint: str, *, session: str | None = None, ip: str | None = None, **form):
		"""Call a whitelisted guest function inside a simulated POST request, as Guest."""
		headers = {"User-Agent": "SecurityTest/1.0"}
		if session:
			headers[guest.SESSION_HEADER] = session
		self.addCleanup(self.end_request)
		# set_user resets form_dict, so switch user before building the request.
		with self.as_user("Guest"):
			set_request(method="POST", path=f"/api/method/frappe_sign.api.guest.{endpoint}", headers=headers)
			frappe.local.request_ip = ip or self.ip
			frappe.local.form_dict = frappe._dict(cmd=f"frappe_sign.api.guest.{endpoint}", **form)
			frappe.local.response = frappe._dict()
			return getattr(guest, endpoint)(**form)

	def end_request(self):
		frappe.local.request = None
		frappe.local.request_ip = None
		frappe.local.form_dict = frappe._dict()

	def error_code(self, endpoint: str, **kwargs) -> str:
		with self.assertRaises(FrappeSignError):
			self.call(endpoint, **kwargs)
		return frappe.local.response.get("code")


class TestEndpoints(GuestApiCase):
	def test_every_endpoint_is_post_only_guest_and_rate_limited(self):
		tree = ast.parse(Path(inspect.getfile(guest)).read_text())
		endpoints = []
		for node in tree.body:
			if not isinstance(node, ast.FunctionDef):
				continue
			decorators = [ast.unparse(d) for d in node.decorator_list]
			if not any(d.startswith("frappe.whitelist") for d in decorators):
				continue
			endpoints.append(node.name)
			self.assertIn("frappe.whitelist(allow_guest=True, methods=['POST'])", decorators, node.name)
			self.assertTrue(
				any(d.startswith("rate_limit(") for d in decorators), f"{node.name} has no rate limit"
			)
		self.assertEqual(
			sorted(endpoints),
			sorted(
				[
					"open",
					"request_otp",
					"verify_otp",
					"state",
					"get_pdf",
					"consent",
					"save_fields",
					"save_capture",
					"finish",
					"decline",
					"delegate",
				]
			),
		)
		for name in endpoints:
			function = getattr(guest, name)
			self.assertIn(function, frappe.guest_methods)
			self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[function], ["POST"])

	def test_errors_carry_a_stable_code(self):
		self.assertEqual(self.error_code("open", token="nope"), "link_expired")
		self.assertEqual(self.error_code("state"), "session_invalid")
		self.assertEqual(self.error_code("state", session="forged"), "session_invalid")

	def test_full_flow_over_the_api(self):
		self.sent()
		opened = self.call("open", token=self.token("Customer"))
		secret = opened["session"]
		self.assertEqual(
			self.error_code("save_fields", session=secret, values='{"customer_name": "A"}'),
			"field_validation_error",
		)
		self.call("consent", session=secret, version=opened["consent"]["version"])
		image = "data:image/png;base64," + base64.b64encode(signature_png()).decode()
		self.call("save_capture", session=secret, field_key="customer_signature", method="Draw", image=image)
		with self.capture_enqueue():
			self.assertEqual(self.call("finish", session=secret), {"status": "Signed", "completed": False})
		self.assertEqual(self.error_code("finish", session=secret), "recipient_done")
		self.assertEqual(frappe.local.response["data"], {"status": "Signed"})

	def test_pdf_is_streamed_privately(self):
		self.sent()
		secret = self.call("open", token=self.token("Customer"))["session"]
		response = self.call("get_pdf", session=secret)
		self.assertEqual(response.mimetype, "application/pdf")
		self.assertEqual(response.headers["Cache-Control"], "no-store")
		self.assertTrue(response.headers["Content-Disposition"].startswith("inline"))
		self.assertEqual(response.headers["Referrer-Policy"], "no-referrer")
		original = frappe.db.get_value("Sign Envelope", self.name, "original_file")
		self.assertEqual(response.get_data(), read_file(original))
		self.assertNotIn("Set-Cookie", response.headers)

	def test_bad_upload_is_refused(self):
		self.sent()
		opened = self.call("open", token=self.token("Customer"))
		self.call("consent", session=opened["session"], version=opened["consent"]["version"])
		code = self.error_code(
			"save_capture",
			session=opened["session"],
			field_key="customer_signature",
			method="Draw",
			image="%%%",
		)
		self.assertEqual(code, "field_validation_error")


class TestRateLimits(GuestApiCase):
	def hammer(self, endpoint: str, times: int, **form) -> None:
		for _ in range(times):
			try:
				self.call(endpoint, **form)
			except FrappeSignError:
				pass  # the domain error is expected; only the rate limit matters here

	def test_open_allows_30_per_minute_per_ip(self):
		self.hammer("open", 30, token="nope")
		self.assertRaises(frappe.RateLimitExceededError, self.call, "open", token="nope")
		self.assertRaises(FrappeSignError, self.call, "open", token="nope", ip=random_ip())

	def test_verify_otp_allows_10_per_10_minutes(self):
		self.hammer("verify_otp", 10, token="nope", code="123456")
		self.assertRaises(frappe.RateLimitExceededError, self.call, "verify_otp", token="nope", code="123456")

	def test_save_fields_allows_120_per_minute(self):
		self.hammer("save_fields", 120, values="{}")
		self.assertRaises(frappe.RateLimitExceededError, self.call, "save_fields", values="{}")

	def test_request_otp_is_keyed_by_recipient_not_ip(self):
		self.sent(otp_mode="Email")
		token = self.token("Customer")
		for _ in range(5):
			try:
				self.call("request_otp", token=token, channel="Email", ip=random_ip())
			except FrappeSignError:
				pass  # cooldown between codes
		self.assertRaises(
			frappe.RateLimitExceededError,
			self.call,
			"request_otp",
			token=token,
			channel="Email",
			ip=random_ip(),
		)
		keys = [key.decode() for key in frappe.cache.get_keys("rl:frappe_sign.api.guest.request_otp")]
		self.assertTrue(keys)
		self.assertTrue(all(token not in key for key in keys), "the token must not appear in Redis keys")
		self.assertTrue(any(sha256_hex(token) in key for key in keys))


class TestScoping(GuestApiCase):
	def test_a_session_cannot_touch_another_envelope(self):
		self.sent()
		mine = self.name
		other = make_draft()
		with capture_tokens() as other_box:
			send_now(other.name)
		other_token = other_box[recipients_by_role(other.name)["Customer"].name]
		opened = self.call("open", token=self.token("Customer"))
		secret = opened["session"]
		self.call("consent", session=secret, version=opened["consent"]["version"])
		other_field = next(
			f
			for f in frappe.get_doc("Sign Envelope", other.name).fields
			if f.role_label == "Customer" and f.field_type == "Full Name"
		)
		other_field_key_value = '{"%s": "hijack"}' % other_field.field_key
		# Field keys repeat across envelopes; the session still writes only its own envelope.
		self.call("save_fields", session=secret, values=other_field_key_value)
		self.assertNotEqual(frappe.db.get_value("Sign Envelope Field", other_field.name, "value"), "hijack")
		pdf = self.call("get_pdf", session=secret).get_data()
		self.assertEqual(sha256_hex(pdf), frappe.db.get_value("Sign Envelope", mine, "original_sha256"))
		state = self.call("state", session=secret)
		self.assertEqual(state["envelope"]["title"], frappe.db.get_value("Sign Envelope", mine, "title"))
		self.assertNotIn(other.name, frappe.as_json(state))
		# The other envelope's token gives its own session, not access to this one.
		other_secret = self.call("open", token=other_token)["session"]
		self.assertEqual(
			self.error_code("save_fields", session=other_secret, values='{"customer_name": "x"}'),
			"field_validation_error",
		)

	def test_company_fields_are_not_the_customers(self):
		self.sent(signing_order="Parallel")
		opened = self.call("open", token=self.token("Customer"))
		self.call("consent", session=opened["session"], version=opened["consent"]["version"])
		code = self.error_code(
			"save_capture",
			session=opened["session"],
			field_key="company_signature",
			method="Draw",
			image=base64.b64encode(signature_png()).decode(),
		)
		self.assertEqual(code, "field_validation_error")
		self.assertEqual(
			{f["key"] for f in opened["fields"]}, {"customer_signature", "customer_name", "customer_date"}
		)
		self.assertNotIn("fatima@example.com", frappe.as_json(opened))

	def test_token_reuse_after_resend_is_denied(self):
		self.sent()
		old = self.token("Customer")
		customer = recipients_by_role(self.name)["Customer"].name
		envelope_service.resend(self.name, customer)
		self.assertEqual(self.error_code("open", token=old), "link_expired")
		self.assertTrue(self.call("open", token=self.token("Customer"))["session"])

	def test_resend_ends_open_sessions(self):
		self.sent()
		secret = self.call("open", token=self.token("Customer"))["session"]
		envelope_service.resend(self.name, recipients_by_role(self.name)["Customer"].name)
		self.assertEqual(self.error_code("state", session=secret), "session_invalid")
