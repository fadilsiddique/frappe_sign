"""Bulk send from the list view (P3.3): one Sign Bulk Run per click, one result per document."""

from unittest.mock import patch

import frappe

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.jobs import bulk
from frappe_sign.services import documents
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_template, make_user
from frappe_sign.tests.integration.test_sealing import no_commits

SENDER = "bulk-sender@example.com"


class BulkCase(SignTestCase):
	def setUp(self):
		super().setUp()
		make_user(SENDER, "Sign User")
		self.template = make_template().name
		self.notes = [f"BULK-NOTE-{n:03d}" for n in range(100)]

	def queue(self, names):
		with self.as_user(SENDER), self.capture_enqueue() as calls:
			result = documents.queue_bulk_send("Note", names, self.template)
		return result, calls

	def run_job(self, run, send, realtime=None):
		with (
			no_commits(),
			patch.object(documents, "send_resolved", side_effect=send),
			patch("frappe.publish_realtime", side_effect=realtime or (lambda *a, **k: None)),
			self.as_user(SENDER),
		):
			bulk.run(run)


class TestQueue(BulkCase):
	def test_creates_a_run_with_one_item_per_document_and_queues_it_long(self):
		result, calls = self.queue(self.notes[:3] + self.notes[:1])
		self.assertEqual(result["queued"], 3)
		job = calls[0]
		self.assertEqual((job["method"], job["queue"]), ("frappe_sign.jobs.bulk.run", "long"))
		run = frappe.get_doc("Sign Bulk Run", job["run"])
		self.assertEqual((run.status, run.total, run.owner), ("Queued", 3, SENDER))
		self.assertEqual([item.document for item in run.items], self.notes[:3])

	def test_limits_and_empty_selection(self):
		self.assertRaises(FieldValidationError, self.queue, [])
		self.assertRaises(FieldValidationError, self.queue, [f"N{n}" for n in range(101)])

	def test_sign_user_sees_only_their_own_runs(self):
		self.queue(self.notes[:1])
		other = make_user("bulk-other@example.com", "Sign User").name
		with self.as_user(SENDER):
			self.assertEqual(len(frappe.get_list("Sign Bulk Run")), 1)
		with self.as_user(other):
			self.assertEqual(frappe.get_list("Sign Bulk Run"), [])


class TestRun(BulkCase):
	def test_hundred_documents_are_processed_and_each_result_is_logged(self):
		result, _calls = self.queue(self.notes)
		run = result["run"]
		broken = {self.notes[7], self.notes[42]}
		events = []

		def send(doctype, name, template):
			if name in broken:
				raise FieldValidationError(f"No email address found for Customer on {name}.")
			return f"SIGN-{name}"

		def collect(event, message=None, **kwargs):
			if event == "frappe_sign_bulk":
				events.append(message)

		self.run_job(run, send, collect)
		doc = frappe.get_doc("Sign Bulk Run", run)
		self.assertEqual((doc.status, doc.total, doc.sent, doc.failed), ("Done", 100, 98, 2))
		results = {item.document: item for item in doc.items}
		self.assertEqual(results[self.notes[0]].status, "Sent")
		self.assertEqual(results[self.notes[0]].envelope, f"SIGN-{self.notes[0]}")
		self.assertEqual(results[self.notes[7]].status, "Failed")
		self.assertIn("No email address", results[self.notes[7]].error)
		self.assertEqual(len(events), 101, "one progress message per document and a final one")
		self.assertEqual((events[49]["done"], events[49]["total"]), (50, 100))
		self.assertEqual(events[-1]["status"], "Done")
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"reference_name": self.notes[7], "method": "Frappe Sign: bulk send"}
			)
		)
		note = frappe.get_last_doc("Notification Log", filters={"document_type": "Sign Bulk Run"})
		self.assertIn("98 of 100", note.subject)

	def test_each_document_commits_on_its_own(self):
		result, _calls = self.queue(self.notes[:3])
		commits = []
		with patch.object(frappe.db, "commit", side_effect=lambda *a, **k: commits.append(1)):
			with (
				patch.object(documents, "send_resolved", return_value="x"),
				patch("frappe.publish_realtime"),
				self.as_user(SENDER),
				patch.object(frappe.db, "rollback"),
			):
				bulk.run(result["run"])
		self.assertGreaterEqual(len(commits), 3)

	def test_a_run_that_is_not_queued_is_ignored(self):
		result, _calls = self.queue(self.notes[:2])
		run = result["run"]
		frappe.db.set_value("Sign Bulk Run", run, "status", "Done")
		self.run_job(run, AssertionError("must not send"))
		self.assertEqual(frappe.db.get_value("Sign Bulk Run", run, "sent"), 0)
