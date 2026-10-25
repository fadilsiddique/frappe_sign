"""Sign Triggers and lifecycle sync through the cached `*` dispatcher (P2.8, D8, DESIGN 4.7)."""

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_sign.jobs import triggers as trigger_jobs
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import gate, trigger
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf, make_user
from frappe_sign.tests.integration.test_resolvers import publish, role
from frappe_sign.tests.integration.test_sealing import no_commits
from frappe_sign.tests.printing import make_print_format
from frappe_sign.tests.signing_helpers import send_now

OWNER = "sign-trigger-owner@example.com"
EDITOR = "plain-editor@example.com"


class DispatcherCase(SignTestCase):
	def setUp(self):
		super().setUp()
		gate.clear()
		self.addCleanup(gate.clear)
		make_user(OWNER, "Sign Manager")
		make_user(EDITOR)
		self.print_format = make_print_format("ToDo", "<p>{{ doc.description }}</p>", "chrome")

	def make_trigger(self, **values):
		template = values.pop("template", None) or publish(
			[role("Owner", "Doc Field", source_field="allocated_to")], print_format=self.print_format.name
		)
		with self.as_user(OWNER):
			return frappe.get_doc(
				{
					"doctype": "Sign Trigger",
					"reference_doctype": "ToDo",
					"event": "Save",
					"template": template,
					"mode": "Create Draft",
					**values,
				}
			).insert()

	def save_todo(self, **values):
		"""Insert a ToDo as a user without Sign roles; returns it and the jobs it queued."""
		with self.as_user(EDITOR), self.capture_enqueue() as calls:
			todo = frappe.get_doc(
				# Allocated to the trigger's owner, who runs the trigger and must be able to read it;
				# assigned by the editor, which v16.0.0's ToDo permission hook needs to let them create it.
				{
					"doctype": "ToDo",
					"description": "Sign me",
					"allocated_to": OWNER,
					"assigned_by": EDITOR,
					**values,
				}
			).insert()
		return todo, calls

	def run_jobs(self, calls):
		for call in ours(calls):
			kwargs = {
				key: value
				for key, value in call.items()
				if key in ("trigger", "doctype", "name", "envelope", "action", "reason")
			}
			job = trigger_jobs.run if call["method"] == trigger.RUN_JOB else trigger_jobs.lifecycle
			with no_commits(), patch("frappe.enqueue"):
				job(**kwargs)

	def logs(self, name):
		return frappe.get_all(
			"Sign Trigger Log",
			filters={"reference_doctype": "ToDo", "reference_name": name},
			fields=["status", "envelope", "error", "owner"],
		)


def ours(calls: list[dict]) -> list[dict]:
	"""The dispatcher's jobs among everything enqueued (Frappe queues jobs of its own too)."""
	return [call for call in calls if call["method"] in (trigger.RUN_JOB, trigger.LIFECYCLE_JOB)]


class TestGate(DispatcherCase):
	def test_non_matching_doctype_costs_one_cache_lookup_and_no_query(self):
		gate.gated_doctypes()  # warm
		note = frappe.get_doc({"doctype": "Note", "title": "Not gated"})
		with (
			patch.object(frappe.cache, "get_value", wraps=frappe.cache.get_value) as lookups,
			patch.object(frappe.db, "sql", wraps=frappe.db.sql) as queries,
		):
			trigger.dispatch(note, "on_update")
		self.assertEqual(lookups.call_count, 1)
		self.assertEqual(queries.call_count, 0)

	def test_gate_holds_triggers_enabled_doctypes_and_open_envelopes(self):
		self.assertNotIn("ToDo", gate.gated_doctypes())
		self.make_trigger()
		self.assertIn("ToDo", gate.gated_doctypes())

	def test_sending_an_envelope_opens_the_gate_for_its_doctype(self):
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Gate", "allocated_to": "Administrator"}
		).insert()
		self.assertNotIn("ToDo", gate.gated_doctypes())
		draft = envelope_service.create_draft(
			{
				"reference_doctype": "ToDo",
				"reference_name": todo.name,
				"print_format": self.print_format.name,
				"recipients": [
					{"role_label": "Owner", "full_name": "Ahmed Khan", "email": "ahmed@example.com"}
				],
			}
		)
		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=fixture_pdf()):
			send_now(draft.name)
		self.assertIn("ToDo", gate.gated_doctypes())

	def test_install_and_migrate_skip_the_dispatcher(self):
		self.make_trigger()
		frappe.flags.in_migrate = True
		self.addCleanup(setattr, frappe.flags, "in_migrate", False)
		_todo, calls = self.save_todo()
		self.assertEqual(calls, [])


class TestTriggers(DispatcherCase):
	def test_save_trigger_creates_a_draft_as_the_trigger_owner(self):
		self.make_trigger()
		todo, calls = self.save_todo()
		self.assertEqual([call["method"] for call in calls], [trigger.RUN_JOB])
		self.assertTrue(calls[0]["enqueue_after_commit"])
		self.run_jobs(calls)
		[log] = self.logs(todo.name)
		self.assertEqual((log.status, log.owner), ("Created", OWNER))
		envelope = frappe.get_doc("Sign Envelope", log.envelope)
		self.assertEqual(
			(envelope.status, envelope.sender, envelope.reference_name), ("Draft", OWNER, todo.name)
		)
		self.assertEqual(envelope.recipients[0].email, OWNER)

	def test_send_mode_sends(self):
		self.make_trigger(mode="Send")
		todo, calls = self.save_todo()
		self.run_jobs(calls)
		[log] = self.logs(todo.name)
		self.assertEqual(log.status, "Sent", log.error and log.error[-400:])
		self.assertEqual(frappe.db.get_value("Sign Envelope", log.envelope, "send_state"), "Queued")

	def test_false_condition_and_open_envelope_skip(self):
		self.make_trigger(condition="doc.priority == 'High'")
		todo, calls = self.save_todo(priority="Low")
		self.run_jobs(calls)
		self.assertEqual([log.status for log in self.logs(todo.name)], ["Skipped"])

		frappe.db.set_value("ToDo", todo.name, "priority", "High")
		self.run_jobs(calls)
		self.run_jobs(calls)
		statuses = sorted(log.status for log in self.logs(todo.name))
		self.assertEqual(statuses, ["Created", "Skipped", "Skipped"])

	def test_value_change_fires_only_on_a_change(self):
		self.make_trigger(event="Value Change", watch_field="status")
		todo, calls = self.save_todo()
		self.assertEqual(calls, [])
		with self.as_user(EDITOR), self.capture_enqueue() as calls:
			todo.reload()
			todo.description = "Edited"
			todo.save()
		self.assertEqual(calls, [])
		with self.as_user(EDITOR), self.capture_enqueue() as calls:
			todo.status = "Closed"
			todo.save()
		self.assertEqual([call["method"] for call in calls], [trigger.RUN_JOB])

	def test_disabled_trigger_does_nothing(self):
		self.make_trigger(enabled=0)
		_todo, calls = self.save_todo()
		self.assertEqual(calls, [])

	def test_failure_is_logged_and_shown_on_the_document(self):
		self.make_trigger()
		frappe.db.set_value(
			"Sign Template", frappe.get_all("Sign Template", pluck="name")[0], "published_version", None
		)
		todo, calls = self.save_todo()
		self.run_jobs(calls)
		[log] = self.logs(todo.name)
		self.assertEqual(log.status, "Failed")
		self.assertIn("no published version", log.error)
		self.assertTrue(
			frappe.db.exists("Error Log", {"method": "Frappe Sign: trigger", "reference_name": todo.name})
		)
		self.assertTrue(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "ToDo",
					"reference_name": todo.name,
					"content": ["like", "%trigger%failed%"],
				},
			)
		)

	def test_triggers_on_frappe_sign_doctypes_are_refused(self):
		with self.assertRaises(frappe.ValidationError):
			self.make_trigger(reference_doctype="Sign Envelope")


class TestLifecycle(DispatcherCase):
	def sent_todo(self):
		todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Contract", "allocated_to": "Administrator"}
		).insert()
		draft = envelope_service.create_draft(
			{
				"reference_doctype": "ToDo",
				"reference_name": todo.name,
				"print_format": self.print_format.name,
				"recipients": [
					{"role_label": "Owner", "full_name": "Ahmed Khan", "email": "ahmed@example.com"}
				],
			}
		)
		with patch("frappe.utils.pdf.get_chrome_pdf", return_value=fixture_pdf()):
			send_now(draft.name)
		gate.clear()
		return todo, draft.name

	def test_delete_voids_open_envelopes(self):
		todo, envelope = self.sent_todo()
		with self.capture_enqueue() as calls:
			frappe.delete_doc("ToDo", todo.name)
		self.assertEqual([(c["action"], c["envelope"]) for c in ours(calls)], [("void", envelope)])
		self.run_jobs(calls)
		doc = frappe.get_doc("Sign Envelope", envelope)
		self.assertEqual(doc.status, "Voided")
		self.assertIn("deleted", doc.void_reason)

	def test_a_change_flags_source_changed_once(self):
		todo, envelope = self.sent_todo()
		with self.capture_enqueue() as calls:
			todo.save()  # nothing changed
		self.assertEqual(calls, [])
		with self.capture_enqueue() as calls:
			todo.description = "Contract, new terms"
			todo.save()
		self.run_jobs(calls)
		self.run_jobs(calls)
		self.assertEqual(frappe.db.get_value("Sign Envelope", envelope, "source_changed"), 1)
		events = frappe.get_all("Sign Event", filters={"envelope": envelope, "event": "Source Changed"})
		self.assertEqual(len(events), 1)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"document_name": envelope, "subject": ["like", "%Void and resend%"]}
			)
		)

	def test_closed_envelopes_are_left_alone(self):
		todo, envelope = self.sent_todo()
		envelope_service.void(envelope, "Wrong")
		with self.capture_enqueue() as calls:
			frappe.delete_doc("ToDo", todo.name)
		self.assertEqual(ours(calls), [])


if __name__ == "__main__":
	unittest.main()
