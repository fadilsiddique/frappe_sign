"""Domain events (P1.11, D17): handlers run in jobs after commit, as the sender, and commit."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from frappe_sign.jobs import events as events_job
from frappe_sign.jobs import seal as seal_job
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import events, notify, signing
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_envelope, make_profile, make_user, test_company
from frappe_sign.tests.integration.test_sealing import no_commits, offline_seal
from frappe_sign.tests.integration.test_signing_service import SigningCase

MARK = "frappe_sign event test"


def writing_handler(envelope: str) -> None:
	frappe.get_doc({"doctype": "ToDo", "description": f"{MARK} ok {envelope}"}).insert()


def failing_handler(envelope: str) -> None:
	frappe.get_doc({"doctype": "ToDo", "description": f"{MARK} half {envelope}"}).insert()
	raise RuntimeError("handler broke")


SEEN_USERS: list[str] = []


def whoami_handler(envelope: str) -> None:
	SEEN_USERS.append(frappe.session.user)


HANDLERS = [f"{__name__}.writing_handler", f"{__name__}.failing_handler", f"{__name__}.whoami_handler"]


class TestPublish(SignTestCase):
	def test_one_job_per_handler_after_commit(self):
		with self.capture_enqueue() as calls:
			events.publish("envelope_completed", "SIGN-X")
		self.assertEqual(
			[(c["method"], c["handler"], c["enqueue_after_commit"]) for c in calls],
			[(events.JOB, handler, True) for handler in events.handlers("envelope_completed")],
		)
		self.assertIn("frappe_sign.services.notify.on_completed", events.handlers("envelope_completed"))

	def test_nothing_is_queued_before_the_transaction_commits(self):
		queue = MagicMock()
		with (
			patch("frappe.utils.background_jobs.get_queue", return_value=queue),
			patch("frappe.utils.background_jobs._check_queue_size"),
		):
			events.publish("envelope_sent", "SIGN-X")
			queue.enqueue_call.assert_not_called()
			frappe.db.after_commit.run()
		self.assertEqual(queue.enqueue_call.call_count, len(events.handlers("envelope_sent")))
		kwargs = queue.enqueue_call.call_args.kwargs["kwargs"]
		self.assertEqual(kwargs["method"], events.JOB)
		self.assertEqual(kwargs["kwargs"]["envelope"], "SIGN-X")

	def test_handlers_run_as_the_sender(self):
		make_user("events.sender@example.com", "Sign User")
		with self.as_user("events.sender@example.com"):
			envelope = make_envelope().name
		SEEN_USERS.clear()
		with patch.object(events, "handlers", return_value=HANDLERS), self.as_user("Guest"):
			events.run_handler(f"{__name__}.whoami_handler", "recipient_signed", envelope)
			self.assertEqual(frappe.session.user, "Guest")
		self.assertEqual(SEEN_USERS, ["events.sender@example.com"])

	def test_unknown_events_and_handlers_are_refused(self):
		self.assertRaises(ValueError, events.publish, "envelope_exploded", "SIGN-X")
		self.assertRaises(
			ValueError, events.run_handler, f"{__name__}.writing_handler", "envelope_sent", "SIGN-X"
		)


class TestEventJob(IntegrationTestCase):
	"""The job commits, so these tests commit too and clean up after themselves."""

	def setUp(self):
		super().setUp()
		self.started = now_datetime()
		self.addCleanup(self.purge)
		patcher = patch.object(events, "handlers", return_value=HANDLERS)
		patcher.start()
		self.addCleanup(patcher.stop)

	def purge(self):
		frappe.db.rollback()
		frappe.db.delete("ToDo", {"description": ["like", f"{MARK}%"]})
		frappe.db.delete(
			"Error Log", {"creation": [">=", self.started], "method": ["like", "Frappe Sign: event%"]}
		)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (clean up committed test rows)

	def todos(self) -> list[str]:
		frappe.db.rollback()  # read what other transactions committed
		return frappe.get_all("ToDo", filters={"description": ["like", f"{MARK}%"]}, pluck="description")

	def test_handler_writes_persist(self):
		events_job.run(f"{__name__}.writing_handler", "envelope_completed", "SIGN-T1")
		self.assertEqual(self.todos(), [f"{MARK} ok SIGN-T1"])

	def test_failing_handler_rolls_back_only_itself(self):
		frappe.get_doc({"doctype": "ToDo", "description": f"{MARK} signature"}).insert()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (stands for the committed signature)
		events_job.run(f"{__name__}.failing_handler", "envelope_completed", "SIGN-T2")
		self.assertEqual(self.todos(), [f"{MARK} signature"])
		log = frappe.get_all(
			"Error Log",
			filters={
				"method": "Frappe Sign: event handler envelope_completed",
				"creation": [">=", self.started],
			},
			fields=["error", "reference_name"],
		)
		self.assertEqual(log[0].reference_name, "SIGN-T2")
		self.assertIn("handler broke", log[0].error)


class TestNotify(SignTestCase):
	def test_fixtures_match_the_fallback_texts(self):
		fixture = Path(frappe.get_app_path("frappe_sign", "fixtures", "email_template.json"))
		rows = {
			row["name"]: (row["subject"], row["response_html"]) for row in json.loads(fixture.read_text())
		}
		self.assertEqual(rows, {name: tuple(texts) for name, texts in notify.FALLBACK.items()})

	def test_email_template_is_used_when_present(self):
		if not frappe.db.exists("Email Template", notify.DECLINED):
			frappe.get_doc(
				{
					"doctype": "Email Template",
					"name": notify.DECLINED,
					"subject": "x",
					"use_html": 1,
					"response_html": "x",
				}
			).insert()
		frappe.db.set_value(
			"Email Template",
			notify.DECLINED,
			{"subject": "Custom {{ envelope_title }}", "use_html": 1, "response_html": "<p>{{ reason }}</p>"},
		)
		subject, message = notify.render(notify.DECLINED, {"envelope_title": "NDA", "reason": "No"})
		self.assertEqual((subject, message.strip()), ("Custom NDA", "<p>No</p>"))

	def test_fallback_when_the_template_was_deleted(self):
		frappe.db.delete("Email Template", {"name": notify.VOIDED})
		subject, message = notify.render(
			notify.VOIDED, {"envelope_title": "NDA", "sender_name": "Fatima", "reason": ""}
		)
		self.assertEqual(subject, "Cancelled: NDA")
		self.assertIn("Fatima cancelled", message)

	def test_user_text_is_escaped(self):
		context = notify.base_context(
			frappe._dict(
				name="SIGN-1", title="<script>x</script>", message="<b>hi</b>", sender=None, company=None
			)
		)
		self.assertNotIn("<script>", context["envelope_title"])
		self.assertNotIn("<b>", context["message"])


class TestNotifyHandlers(SigningCase):
	def emails(self, name: str) -> list:
		return frappe.get_all(
			"Email Queue",
			filters={"reference_name": name},
			fields=["name", "message", "attachments"],
			order_by="creation asc",
		)

	def recipients_of(self, queue: str) -> set[str]:
		return set(frappe.get_all("Email Queue Recipient", filters={"parent": queue}, pluck="recipient"))

	def test_completed_mails_everyone_the_sealed_pdf(self):
		make_profile(test_company())
		self.sent(company=test_company())
		frappe.db.set_value("Sign Envelope", self.name, "company", test_company())
		self.sign("Customer")
		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		before = len(self.emails(self.name))
		notify.on_completed(self.name)
		email = self.emails(self.name)[before]
		self.assertEqual(
			self.recipients_of(email.name), {"ahmed@example.com", "fatima@example.com", "admin@example.com"}
		)
		self.assertIn(frappe.db.get_value("Sign Envelope", self.name, "signed_file"), email.attachments)

	def test_declined_tells_the_sender(self):
		self.sent()
		with self.capture_enqueue():
			signing.decline(self.start(), "Too expensive")
		notify.on_declined(self.name)
		email = self.emails(self.name)[-1]
		self.assertIn("Too expensive", email.message)
		self.assertEqual(self.recipients_of(email.name), {"admin@example.com"})

	def test_voided_tells_invited_recipients_only(self):
		self.sent()
		with self.capture_enqueue():
			envelope_service.void(self.name, "Wrong price")
		notify.on_voided(self.name)
		email = self.emails(self.name)[-1]
		self.assertEqual(self.recipients_of(email.name), {"ahmed@example.com"})
		self.assertIn("Wrong price", email.message)

	def test_signed_notifies_the_sender_in_desk(self):
		make_user("notify.sender@example.com", "Sign User")
		self.sent()
		frappe.db.set_value("Sign Envelope", self.name, "sender", "notify.sender@example.com")
		self.sign("Customer")
		with self.as_user("notify.sender@example.com"):
			notify.on_signed(self.name)
		log = frappe.get_all(
			"Notification Log", filters={"document_name": self.name}, fields=["for_user", "subject"]
		)
		self.assertEqual(log[0].for_user, "notify.sender@example.com")
		self.assertIn("Ahmed Khan", log[0].subject)
