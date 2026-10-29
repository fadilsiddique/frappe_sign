"""Health panel (P3.7): the checks, their statuses and the people who may see them."""

import json
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_days, now_datetime

from frappe_sign.services import health
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_certificate, make_envelope, make_profile, make_user, test_company


def by_key(report: dict) -> dict:
	return {check["key"]: check for check in report["checks"]}


class HealthCase(SignTestCase):
	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.cache.delete_value, health.TSA_CACHE)
		frappe.cache.delete_value(health.TSA_CACHE)
		self.start_clean()

	def start_clean(self):
		"""The dev site has real profiles, stuck seals and failed runs; the checks look at all of
		them, so the test transaction clears them (it never commits, and rolls back)."""
		self.refuse_commits()
		frappe.db.delete("Sign Profile")
		frappe.db.delete("Sign Trigger Log")
		frappe.db.sql(
			"update `tabSign Envelope` set sealing_state = 'Not Started' where sealing_state != 'Sealed'"
		)

	def report(self, refresh=True, **patches) -> dict:
		defaults = {"probe_tsa": lambda url: None, "lookup_txt": lambda name: None}
		with (
			patch.object(health, "probe_tsa", side_effect=patches.get("probe_tsa", defaults["probe_tsa"])),
			patch.object(health, "lookup_txt", side_effect=patches.get("lookup_txt", defaults["lookup_txt"])),
		):
			return health.report(refresh=refresh)

	def profile_with_seal_ending_in(self, days: int):
		certificate = make_certificate()
		frappe.db.set_value("Sign Certificate", certificate.name, "valid_to", add_days(now_datetime(), days))
		return make_profile(test_company(), sealing_certificate=certificate.name)


class TestSeal(HealthCase):
	def test_ok_warn_and_fail_by_days_left(self):
		self.profile_with_seal_ending_in(200)
		self.assertEqual(by_key(self.report())["seal"]["status"], "ok")
		frappe.db.set_value(
			"Sign Certificate",
			frappe.db.get_value("Sign Profile", test_company(), "sealing_certificate"),
			"valid_to",
			add_days(now_datetime(), 10),
		)
		check = by_key(self.report())["seal"]
		self.assertEqual(check["status"], "warn")
		frappe.db.set_value(
			"Sign Certificate",
			frappe.db.get_value("Sign Profile", test_company(), "sealing_certificate"),
			"valid_to",
			add_days(now_datetime(), -1),
		)
		self.assertEqual(by_key(self.report())["seal"]["status"], "fail")

	def test_a_profile_without_a_certificate_fails(self):
		frappe.get_doc({"doctype": "Sign Profile", "company": test_company()}).insert()
		self.assertEqual(by_key(self.report())["seal"]["status"], "fail")

	def test_the_detail_names_the_company(self):
		self.profile_with_seal_ending_in(200)
		self.assertIn(test_company(), by_key(self.report())["seal"]["detail"])


class TestTimestamps(HealthCase):
	def test_all_up_some_down_all_down(self):
		frappe.db.set_single_value("Sign Settings", "tsa_urls", "http://a.test\nhttp://b.test")
		self.assertEqual(by_key(self.report())["tsa"]["status"], "ok")
		self.assertEqual(
			by_key(self.report(probe_tsa=lambda url: "down" if "a.test" in url else None))["tsa"]["status"],
			"warn",
		)
		check = by_key(self.report(probe_tsa=lambda url: "no answer"))["tsa"]
		self.assertEqual(check["status"], "fail")
		self.assertIn("a.test", check["detail"])

	def test_the_result_is_cached_until_refreshed(self):
		calls = []
		self.report(probe_tsa=lambda url: calls.append(url))
		first = len(calls)
		self.report(refresh=False, probe_tsa=lambda url: calls.append(url))
		self.assertEqual(len(calls), first)
		self.report(refresh=True, probe_tsa=lambda url: calls.append(url))
		self.assertGreater(len(calls), first)


class TestSeals(HealthCase):
	def queue(self, state, minutes_ago):
		envelope = make_envelope()
		frappe.db.set_value(
			"Sign Envelope",
			envelope.name,
			{
				"status": "In Progress",
				"sealing_state": state,
				"modified": now_datetime() - timedelta(minutes=minutes_ago),
			},
			update_modified=False,
		)
		return envelope

	def test_no_queue_is_ok(self):
		self.assertEqual(by_key(self.report())["seals"]["status"], "ok")

	def test_age_of_the_oldest_queued_seal(self):
		envelope = self.queue("Queued", 5)
		self.assertEqual(by_key(self.report())["seals"]["status"], "ok")
		frappe.db.set_value(
			"Sign Envelope",
			envelope.name,
			"modified",
			now_datetime() - timedelta(minutes=30),
			update_modified=False,
		)
		self.assertEqual(by_key(self.report())["seals"]["status"], "warn")
		frappe.db.set_value(
			"Sign Envelope",
			envelope.name,
			"modified",
			now_datetime() - timedelta(hours=3),
			update_modified=False,
		)
		check = by_key(self.report())["seals"]
		self.assertEqual(check["status"], "fail")
		self.assertIn(envelope.name, check["detail"])

	def test_a_failed_seal_fails_the_check(self):
		self.queue("Failed", 1)
		self.assertEqual(by_key(self.report())["seals"]["status"], "fail")


class TestTriggers(HealthCase):
	def log(self, hours_ago):
		trigger = frappe.get_doc(
			{
				"doctype": "Sign Trigger",
				"reference_doctype": "ToDo",
				"event": "Save",
				"template": make_template_name(),
				"mode": "Create Draft",
			}
		).insert()
		log = frappe.get_doc(
			{"doctype": "Sign Trigger Log", "trigger": trigger.name, "status": "Failed"}
		).insert()
		frappe.db.set_value(
			"Sign Trigger Log",
			log.name,
			"creation",
			now_datetime() - timedelta(hours=hours_ago),
			update_modified=False,
		)

	def test_only_failures_in_the_last_24_hours_count(self):
		self.assertEqual(by_key(self.report())["triggers"]["status"], "ok")
		self.log(30)
		self.assertEqual(by_key(self.report())["triggers"]["status"], "ok")
		self.log(2)
		check = by_key(self.report())["triggers"]
		self.assertEqual(check["status"], "warn")
		self.assertIn("1", check["detail"])


def make_template_name() -> str:
	from frappe_sign.tests.factories import make_template

	return make_template().name


class TestEmail(HealthCase):
	def records(self, spf=True, dkim_selector="default"):
		def lookup(name: str):
			if name == "example.com":
				return ["v=spf1 include:_spf.example.com ~all"] if spf else ["something else"]
			if name == f"{dkim_selector}._domainkey.example.com":
				return ["v=DKIM1; k=rsa; p=abc"]
			return []

		return lookup

	def make_profile_for(self):
		make_profile(test_company())
		patcher = patch(
			"frappe_sign.services.health.sender_addresses", return_value={test_company(): "sign@example.com"}
		)
		patcher.start()
		self.addCleanup(patcher.stop)

	def test_found_records_are_ok(self):
		self.make_profile_for()
		check = by_key(self.report(lookup_txt=self.records()))["email"]
		self.assertEqual(check["status"], "ok")

	def test_a_missing_spf_record_warns_with_a_hint(self):
		self.make_profile_for()
		check = by_key(self.report(lookup_txt=self.records(spf=False)))["email"]
		self.assertEqual(check["status"], "warn")
		self.assertIn("SPF", check["detail"])
		self.assertTrue(check["hint"])

	def test_without_dns_access_it_only_gives_hints(self):
		self.make_profile_for()
		check = by_key(self.report())["email"]
		self.assertEqual(check["status"], "info")
		self.assertIn("SPF", check["hint"])
		self.assertIn("DKIM", check["hint"])


class TestReport(HealthCase):
	def test_overall_status_is_the_worst_check(self):
		self.profile_with_seal_ending_in(200)
		self.assertNotEqual(self.report()["status"], "fail")
		certificate = frappe.db.get_value("Sign Profile", test_company(), "sealing_certificate")
		frappe.db.set_value("Sign Certificate", certificate, "valid_to", add_days(now_datetime(), -1))
		self.assertEqual(self.report()["status"], "fail")

	def test_sign_manager_may_look_and_sign_user_may_not(self):
		make_user("health-manager@example.com", "Sign Manager")
		make_user("health-user@example.com", "Sign User")
		with self.as_user("health-manager@example.com"), patch.object(health, "probe_tsa", return_value=None):
			self.assertIn("checks", health.report())
		with self.as_user("health-user@example.com"), self.assertRaises(frappe.PermissionError):
			health.report()

	def test_report_is_json_serializable_and_holds_no_secret(self):
		self.profile_with_seal_ending_in(200)
		text = json.dumps(self.report())
		self.assertNotIn("fixture-seal", text)
