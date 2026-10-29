"""Setup status for the Home "Set up signing" panel (U.3, UX_PLAN "Home")."""

import frappe
from frappe.utils import add_days, now_datetime

from frappe_sign.api import staff
from frappe_sign.services import setup
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_email_account, make_profile, make_user, test_company
from frappe_sign.tests.signing_helpers import make_draft, publish_template, send_now

STEPS = ["email", "seal", "profile", "documents", "template", "test"]
HAS_ERPNEXT = "erpnext" in frappe.get_installed_apps()


def enable_doctype(doctype: str) -> None:
	"""The settings row alone. Saving Sign Settings would add custom fields to the DocType, a schema
	change that commits."""
	frappe.get_doc(
		{
			"doctype": "Sign Enabled DocType",
			"parent": "Sign Settings",
			"parenttype": "Sign Settings",
			"parentfield": "enabled_doctypes",
			"reference_doctype": doctype,
		}
	).db_insert()


class TestSetupStatus(SignTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.refuse_commits()
		# An empty site, inside this test's transaction (rolled back afterwards).
		for doctype in ("Email Account", "Sign Envelope", "Sign Template", "Sign Profile", "Sign Enabled DocType"):
			frappe.db.delete(doctype)

	def steps(self) -> dict:
		return {step["key"]: step for step in setup.setup_status()["steps"]}

	def test_the_deleted_site_data_cannot_be_committed(self):
		self.assertRaises(AssertionError, frappe.db.commit)
		self.assertRaises(AssertionError, frappe.db.sql_ddl, "select 1")

	def test_an_empty_site_has_every_step_to_do(self):
		status = setup.setup_status()
		self.assertEqual([step["key"] for step in status["steps"]], STEPS)
		self.assertFalse(any(step["done"] for step in status["steps"]))
		self.assertFalse(status["complete"])

	def test_email_is_done_with_an_outgoing_account(self):
		make_email_account()
		email = self.steps()["email"]
		self.assertTrue(email["done"])
		self.assertEqual(email["facts"]["email_id"], "sign-test@example.com")

	def test_seal_and_profile(self):
		make_profile(test_company(), brand_color=None)
		steps = self.steps()
		self.assertTrue(steps["seal"]["done"])
		self.assertEqual(steps["seal"]["facts"]["kind"], "Self-signed")
		self.assertTrue(steps["seal"]["facts"]["valid_to"])
		self.assertFalse(steps["profile"]["done"], "a profile without logo or color is not set up yet")
		self.assertEqual(steps["profile"]["facts"]["profile"], test_company())

		frappe.db.set_value("Sign Profile", test_company(), "brand_color", "#0f766e")
		self.assertTrue(self.steps()["profile"]["done"])

	def test_an_expired_seal_is_to_do(self):
		profile = make_profile(test_company())
		frappe.db.set_value("Sign Certificate", profile.sealing_certificate, "valid_to", add_days(now_datetime(), -1))
		seal = self.steps()["seal"]
		self.assertFalse(seal["done"])
		self.assertTrue(seal["facts"]["expired"])

	def test_documents_template_and_test_send(self):
		make_email_account()
		enable_doctype("User")
		self.assertTrue(self.steps()["documents"]["done"])
		self.assertEqual(self.steps()["documents"]["facts"]["doctypes"], ["User"])

		version = publish_template()
		self.assertTrue(self.steps()["template"]["done"])
		self.assertFalse(self.steps()["test"]["done"], "a draft is not a test send")
		send_now(make_draft(version).name)
		self.assertTrue(self.steps()["test"]["done"])

	def test_documents_count_only_with_erpnext(self):
		self.assertEqual(self.steps()["documents"]["required"], HAS_ERPNEXT)

	def test_complete_when_every_required_step_is_done(self):
		make_email_account()
		make_profile(test_company())
		if HAS_ERPNEXT:
			enable_doctype("User")
		send_now(make_draft(publish_template()).name)
		self.assertTrue(setup.setup_status()["complete"])

	def test_who_can_fix_each_step(self):
		self.assertTrue(all(step["can_fix"] for step in setup.setup_status()["steps"]))
		user = make_user("setup-sign-user@example.com", "Sign User")
		with self.as_user(user.name):
			steps = {step["key"]: step["can_fix"] for step in staff.get_setup_status()["steps"]}
		self.assertEqual(
			steps,
			{
				"email": False,
				"seal": False,
				"profile": False,
				"documents": False,
				"template": False,
				"test": True,
			},
		)

	def test_needs_a_sign_role(self):
		user = make_user("setup-no-role@example.com")
		with self.as_user(user.name):
			self.assertRaises(frappe.PermissionError, staff.get_setup_status)
