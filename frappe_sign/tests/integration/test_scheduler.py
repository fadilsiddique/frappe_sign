"""Scheduler jobs (P3.2): reminders, expiry, certificate warnings, session purge and date triggers.

Time is frozen with freezegun, so every test says exactly when the scheduler runs.
"""

from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, now_datetime
from freezegun import freeze_time

from frappe_sign.jobs import housekeeping, reminders
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import gate, schedule, trigger
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_certificate, make_user
from frappe_sign.tests.integration.test_dispatcher import DispatcherCase
from frappe_sign.tests.integration.test_envelope_service import events_of
from frappe_sign.tests.integration.test_sealing import no_commits
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now
from frappe_sign.utils.dates import utc_now


def frozen_in(**delta):
	"""freeze_time at now plus `delta`; Sign Event.at is naive UTC, which freezegun takes as UTC."""
	return freeze_time(utc_now() + timedelta(**delta))


class SchedulerCase(SignTestCase):
	def setUp(self):
		super().setUp()
		# The dev site may hold real open requests; the scheduler looks at every envelope, so the
		# test transaction closes them first (it never commits, and rolls back).
		self.refuse_commits()
		frappe.db.sql(
			"update `tabSign Envelope` set status = 'Voided' where status in ('Sent', 'In Progress')"
		)

	def sent(self, signing_order="Sequential"):
		version = publish_template(signing_order=signing_order)
		draft = make_draft(version)
		with capture_tokens():
			send_now(draft.name)
		return draft.name

	def reminders_of(self, name):
		return [event for event in events_of(name) if event == "Reminded"]

	def set_reminder_days(self, days):
		frappe.db.set_single_value("Sign Settings", "default_reminder_days", days)


class TestReminders(SchedulerCase):
	def tick(self):
		with no_commits(), capture_tokens() as box:
			reminders.run()
		return box

	def test_reminds_after_the_interval_and_not_twice(self):
		self.set_reminder_days(2)
		name = self.sent()
		with frozen_in(days=1):
			self.assertEqual(self.tick().sent, [])
		with frozen_in(days=2, minutes=1):
			box = self.tick()
			self.assertEqual(len(box.sent), 1)
			self.assertTrue(box.sent[0][2], "sent as a reminder")
			self.assertEqual(self.tick().sent, [], "the next run in the same interval stays quiet")
		self.assertEqual(len(self.reminders_of(name)), 1)
		with frozen_in(days=4, minutes=2):
			self.assertEqual(len(self.tick().sent), 1)
		self.assertEqual(len(self.reminders_of(name)), 2)

	def test_only_the_signer_whose_turn_it_is(self):
		self.set_reminder_days(1)
		name = self.sent()
		with frozen_in(days=1, minutes=1):
			box = self.tick()
		rows = {row.role_label: row.name for row in frappe.get_doc("Sign Envelope", name).recipients}
		self.assertEqual([sent[0] for sent in box.sent], [rows["Customer"]])

	def test_switched_off_with_zero_days(self):
		self.set_reminder_days(0)
		self.sent()
		with frozen_in(days=10):
			self.assertEqual(self.tick().sent, [])

	def test_no_reminder_for_a_voided_envelope(self):
		self.set_reminder_days(1)
		name = self.sent()
		envelope_service.void(name, "Wrong draft")
		with frozen_in(days=2):
			self.assertEqual(self.tick().sent, [])


class TestExpiry(SchedulerCase):
	def test_expires_after_expires_on_only(self):
		name = self.sent()
		with frozen_in(days=13):
			self.assertEqual(envelope_service.expire_due(), [])
		with frozen_in(days=15):
			self.assertEqual(envelope_service.expire_due(), [name])
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "status"), "Expired")

	def test_job_reminds_then_expires_and_commits_per_envelope(self):
		self.set_reminder_days(1)
		name = self.sent()
		with frozen_in(days=15), no_commits(), capture_tokens() as box:
			reminders.run()
		self.assertEqual(box.sent, [], "an expired envelope gets no reminder")
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "status"), "Expired")

	def test_one_failing_envelope_does_not_stop_the_others(self):
		first, second = self.sent(), self.sent()
		real = envelope_service.expire

		def flaky(name):
			if name == first:
				raise RuntimeError("boom")
			return real(name)

		with frozen_in(days=15), no_commits(), patch.object(envelope_service, "expire", side_effect=flaky):
			reminders.run()
		self.assertEqual(frappe.db.get_value("Sign Envelope", second, "status"), "Expired")
		self.assertEqual(frappe.db.get_value("Sign Envelope", first, "status"), "Sent")
		self.assertTrue(frappe.db.exists("Error Log", {"method": ["like", "Frappe Sign: scheduler%"]}))


class TestCertificateWarnings(SchedulerCase):
	def make(self, days_left):
		certificate = make_certificate()
		frappe.db.set_value(
			"Sign Certificate", certificate.name, "valid_to", add_days(now_datetime(), days_left)
		)
		return certificate.name

	def warnings(self, certificate):
		return frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Sign Certificate", "reference_name": certificate},
			pluck="content",
		)

	def test_warns_once_per_threshold(self):
		make_user("cert-manager@example.com", "Sign Manager")
		certificate = self.make(40)
		with patch.object(schedule.notify, "notify_user") as notified:
			with frozen_in(days=5):  # 35 days left
				self.assertEqual(schedule.warn_certificate_expiry(), [])
			with frozen_in(days=10, minutes=5):  # 30 days left
				self.assertEqual(schedule.warn_certificate_expiry(), [certificate])
				self.assertEqual(schedule.warn_certificate_expiry(), [], "a second run the same day is quiet")
			with frozen_in(days=11):
				self.assertEqual(schedule.warn_certificate_expiry(), [])
			with frozen_in(days=26, minutes=5):  # 14 days left
				self.assertEqual(schedule.warn_certificate_expiry(), [certificate])
			with frozen_in(days=41):  # ended
				self.assertEqual(schedule.warn_certificate_expiry(), [certificate])
		self.assertEqual(len(self.warnings(certificate)), 3)
		self.assertIn("cert-manager@example.com", {call.args[0] for call in notified.call_args_list})

	def test_ignores_certificates_without_an_end_date(self):
		certificate = make_certificate()
		frappe.db.set_value("Sign Certificate", certificate.name, "valid_to", None)
		self.assertEqual(schedule.warn_certificate_expiry(), [])


class TestSessionPurge(SchedulerCase):
	def test_purges_only_sessions_ended_more_than_a_day_ago(self):
		name = self.sent()
		recipient = frappe.get_doc("Sign Envelope", name).recipients[0].name
		for label, delta in (
			("old", timedelta(days=3)),
			("recent", timedelta(hours=2)),
			("live", -timedelta(hours=1)),
		):
			frappe.get_doc(
				{
					"doctype": "Sign Session",
					"envelope": name,
					"recipient_row": recipient,
					"last_seen_on": now_datetime(),
					"expires_on": now_datetime() - delta,
					"user_agent": label,
				}
			).insert()
		self.assertEqual(schedule.purge_sessions(), 1)
		left = frappe.get_all("Sign Session", filters={"envelope": name}, pluck="user_agent")
		self.assertCountEqual(left, ["recent", "live"])


class TestDateTriggers(DispatcherCase):
	def date_trigger(self, days_offset=-3):
		return self.make_trigger(event="Date", date_field="date", days_offset=days_offset)

	def todo(self, days_from_today):
		name = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": f"Due in {days_from_today}",
				"allocated_to": "sign-trigger-owner@example.com",
				"date": add_days(getdate(), days_from_today),
			}
		).insert()
		return name.name

	def queued(self):
		with self.capture_enqueue() as calls:
			schedule.run_date_triggers()
		return [call for call in calls if call["method"] == trigger.RUN_JOB]

	def test_fires_on_the_day_and_catches_up_a_missed_day(self):
		trigger_doc = self.date_trigger(-3)
		on_day, missed, early, late = self.todo(3), self.todo(2), self.todo(10), self.todo(-20)
		queued = self.queued()
		self.assertCountEqual([call["name"] for call in queued], [on_day, missed])
		self.assertEqual({call["trigger"] for call in queued}, {trigger_doc.name})
		self.assertTrue(all(call["deduplicate"] and call["job_id"] for call in queued))
		self.assertNotIn(early, [call["name"] for call in queued])
		self.assertNotIn(late, [call["name"] for call in queued])

	def test_a_document_runs_once(self):
		trigger_doc = self.date_trigger(0)
		name = self.todo(0)
		self.assertEqual(len(self.queued()), 1)
		trigger.start_log(trigger_doc.name, "ToDo", name)
		self.assertEqual(self.queued(), [])

	def test_disabled_trigger_and_other_events_are_ignored(self):
		self.date_trigger(0).db_set("enabled", 0)
		self.make_trigger(event="Save")
		self.todo(0)
		gate.clear()
		self.assertEqual(self.queued(), [])

	def test_housekeeping_failing_step_does_not_skip_the_others(self):
		with (
			no_commits(),
			patch.object(schedule, "warn_certificate_expiry", side_effect=RuntimeError("boom")),
			patch.object(schedule, "purge_sessions") as purge,
			patch.object(schedule, "run_date_triggers") as dates,
		):
			housekeeping.run()
		purge.assert_called_once()
		dates.assert_called_once()
		self.assertTrue(frappe.db.exists("Error Log", {"method": ["like", "Frappe Sign: scheduler%"]}))

	def test_housekeeping_job_runs_every_step(self):
		with (
			no_commits(),
			patch.object(schedule, "refresh_remote_certificates") as remote,
			patch.object(schedule, "warn_certificate_expiry") as warn,
			patch.object(schedule, "purge_sessions") as purge,
			patch.object(schedule, "run_date_triggers") as dates,
		):
			housekeeping.run()
		for step in (remote, warn, purge, dates):
			step.assert_called_once()
