"""Sealing flow (P1.10, DESIGN 5.4): job, retries with backoff, retry_seal."""

import io
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime
from pypdf import PdfReader

from frappe_sign.exceptions import InvalidTransition
from frappe_sign.jobs import seal as seal_job
from frappe_sign.services import audit, sealing
from frappe_sign.tests import pki
from frappe_sign.tests.factories import make_profile, make_user, test_company
from frappe_sign.tests.integration.test_signing_service import SigningCase
from frappe_sign.utils.files import read_file
from frappe_sign.utils.hashing import sha256_hex


def offline_seal():
	return patch.object(
		sealing,
		"seal_options",
		return_value={
			"timestamper": pki.timestamper(),
			"validation_context": pki.sealing_validation_context(),
		},
	)


def no_commits():
	"""Run job entry points inside the test transaction."""
	return patch.multiple(frappe.db, commit=lambda *a, **k: None, rollback=lambda *a, **k: None)


class TestSealing(SigningCase):
	def fully_signed(self) -> str:
		self.sent(company=test_company())
		frappe.db.set_value("Sign Envelope", self.name, "company", test_company())
		self.sign("Customer")
		self.sign("Company")
		return self.name

	def test_seal_job_completes_the_envelope(self):
		make_profile(test_company())
		name = self.fully_signed()
		with offline_seal(), no_commits(), self.capture_enqueue() as calls:
			seal_job.run(name)
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertEqual((doc.status, doc.sealing_state), ("Completed", "Sealed"))
		sealed = read_file(doc.signed_file)
		self.assertEqual(doc.signed_sha256, sha256_hex(sealed))
		self.assertEqual(frappe.get_doc("File", doc.signed_file).is_private, 1)
		status = pki.validate_lt(sealed)
		self.assertTrue(status.bottom_line, status.pretty_print_details())
		reader = PdfReader(io.BytesIO(sealed))
		self.assertGreaterEqual(len(reader.pages), 2, "document page + certificate pages")
		certificate = "".join(page.extract_text() for page in reader.pages[1:]).replace("\n", "")
		self.assertIn(doc.audit_head, certificate)
		self.assertIn("Ahmed Khan", certificate)
		events = frappe.get_all("Sign Event", filters={"envelope": name}, pluck="event", order_by="seq asc")
		self.assertEqual(events[-2:], ["Sealed", "Completed"])
		report = audit.verify_chain(name)
		self.assertTrue(report.ok)
		self.assertIn(doc.audit_head, frappe.get_all("Sign Event", filters={"envelope": name}, pluck="hash"))
		self.assertIn("envelope_completed", [c.get("domain_event") for c in calls])

	def test_second_job_does_nothing(self):
		make_profile(test_company())
		name = self.fully_signed()
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(name)
			seal_job.run(name)
		self.assertEqual(frappe.db.count("Sign Event", {"envelope": name, "event": "Sealed"}), 1)
		self.assertFalse(sealing.begin(name))

	def test_failures_retry_with_backoff_then_alert(self):
		name = self.fully_signed()  # no Sign Profile, so sealing fails
		for attempt, minutes in enumerate(sealing.BACKOFF_MINUTES, start=1):
			with no_commits():
				seal_job.run(name)
			doc = frappe.get_doc("Sign Envelope", name)
			self.assertEqual((doc.sealing_state, doc.seal_attempts), ("Failed", attempt))
			wait = (doc.seal_retry_on - now_datetime()).total_seconds()
			self.assertAlmostEqual(wait, minutes * 60, delta=5)
			self.assertEqual(sealing.retry_due(), [], "not due yet")
			frappe.db.set_value("Sign Envelope", name, "seal_retry_on", now_datetime() - timedelta(seconds=1))
			with self.capture_enqueue() as calls:
				with no_commits():
					seal_job.retry_due()
			self.assertEqual([c["job_id"] for c in calls], [sealing.job_id(name)])
			self.assertEqual(frappe.db.get_value("Sign Envelope", name, "sealing_state"), "Queued")
		with no_commits():
			seal_job.run(name)
		doc = frappe.get_doc("Sign Envelope", name)
		self.assertEqual((doc.sealing_state, doc.seal_attempts, doc.seal_retry_on), ("Failed", 4, None))
		self.assertEqual(doc.status, "In Progress")
		self.assertTrue(
			frappe.db.exists("Error Log", {"reference_name": name, "method": "Frappe Sign: seal"})
		)
		self.assertTrue(
			frappe.db.exists("Email Queue", {"reference_name": name, "message": ["like", "%Sealing failed%"]})
		)

	def test_retry_seal_is_for_sign_managers_after_failure(self):
		name = self.fully_signed()
		make_user("seal.user@example.com", "Sign User")
		make_user("seal.manager@example.com", "Sign Manager")
		with self.as_user("seal.manager@example.com"):
			self.assertRaises(InvalidTransition, sealing.retry_seal, name)
		with no_commits():
			seal_job.run(name)
		with self.as_user("seal.user@example.com"):
			self.assertRaises(frappe.PermissionError, sealing.retry_seal, name)
		with self.as_user("seal.manager@example.com"), self.capture_enqueue() as calls:
			sealing.retry_seal(name)
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "sealing_state"), "Queued")
		self.assertEqual(calls[0]["job_id"], sealing.job_id(name))
		self.assertTrue(calls[0]["deduplicate"])
