"""Two threads, two database connections (P1.10, DESIGN 5.4 and 9).

1. Two parallel signers finish at the same moment: the envelope row lock puts the finishes in
   order, the audit chain has no fork or gap, and exactly one seal job is enqueued.
2. Two seal jobs run at the same moment: exactly one seal is made.

These tests must commit, because each thread has its own connection. Everything they create is
deleted again in tearDown.
"""

import io
import os
import threading
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_files_path, now_datetime
from pypdf import PdfReader

from frappe_sign.jobs import seal as seal_job
from frappe_sign.services import audit, sealing, signing
from frappe_sign.tests.factories import make_email_account, make_profile
from frappe_sign.tests.integration.test_sealing import COMPANY, offline_seal
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now
from frappe_sign.tests.unit.test_overlay import signature_png
from frappe_sign.utils.files import read_file
from frappe_sign.utils.request import Client
from frappe_sign.utils.users import run_as


def in_thread(site: str, sites_path: str, work, barrier: threading.Barrier, results: dict, key: str) -> None:
	frappe.init(site=site, sites_path=sites_path)
	frappe.connect()
	try:
		barrier.wait(timeout=30)
		results[key] = work()
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (threads need committed rows)
	except Exception as error:
		error.trace = frappe.get_traceback()
		frappe.db.rollback()
		results[key] = error
	finally:
		frappe.destroy()


def run_together(**works) -> dict:
	site, sites_path = frappe.local.site, frappe.local.sites_path
	barrier = threading.Barrier(len(works))
	results: dict = {}
	threads = [
		threading.Thread(target=in_thread, args=(site, sites_path, work, barrier, results, key))
		for key, work in works.items()
	]
	for thread in threads:
		thread.start()
	for thread in threads:
		thread.join(timeout=120)
	return results


class TestConcurrency(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		self.started = now_datetime()
		self.envelope = None
		self.addCleanup(self.purge)
		with run_as("Administrator"):
			make_email_account()
			make_profile(COMPANY)
			version = publish_template(signing_order="Parallel")
			draft = make_draft(version, company=COMPANY)
			with capture_tokens() as box:
				send_now(draft.name)
			self.envelope = draft.name
			client = Client(ip="203.0.113.10", user_agent="test")
			self.secrets = {}
			for row in frappe.get_doc("Sign Envelope", draft.name).recipients:
				opened = signing.open(box[row.name], client)
				signing.consent(opened["session"], opened["consent"]["version"], client)
				key = "customer_signature" if row.role_label == "Customer" else "company_signature"
				signing.save_capture(opened["session"], key, "Draw", signature_png(), client=client)
				self.secrets[row.role_label] = opened["session"]
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (threads need committed rows)

	def test_parallel_finishes_queue_one_seal(self):
		calls = []
		client = Client(ip="203.0.113.11", user_agent="thread")
		with patch("frappe.enqueue", side_effect=lambda method, **kw: calls.append({"method": method, **kw})):
			results = run_together(
				customer=lambda: signing.finish(self.secrets["Customer"], client),
				company=lambda: signing.finish(self.secrets["Company"], client),
			)
		traces = [getattr(value, "trace", "") for value in results.values() if isinstance(value, Exception)]
		self.assertEqual(
			{key: type(value) for key, value in results.items()},
			{"customer": dict, "company": dict},
			"\n".join(traces),
		)
		self.assertEqual(sorted(r["completed"] for r in results.values()), [False, True])
		seals = [call for call in calls if call["method"] == sealing.JOB]
		self.assertEqual(len(seals), 1)
		self.assertEqual(seals[0]["job_id"], sealing.job_id(self.envelope))
		frappe.db.rollback()  # start a fresh read view
		doc = frappe.get_doc("Sign Envelope", self.envelope)
		self.assertEqual((doc.status, doc.sealing_state), ("In Progress", "Queued"))
		seqs = frappe.get_all(
			"Sign Event", filters={"envelope": self.envelope}, pluck="seq", order_by="seq asc"
		)
		self.assertEqual(seqs, list(range(1, len(seqs) + 1)))
		self.assertTrue(audit.verify_chain(self.envelope).ok)
		self.assertEqual(frappe.db.count("Sign Event", {"envelope": self.envelope, "event": "Signed"}), 2)
		# Whoever finished second rendered after the first commit, so its PDF has the Full Name that
		# the Customer's finish fills in, in either order.
		later = max(doc.recipients, key=lambda row: row.signed_on)
		text = PdfReader(io.BytesIO(read_file(later.intermediate_file))).pages[0].extract_text()
		self.assertIn("Ahmed Khan", text)

	def test_two_seal_jobs_seal_once(self):
		with patch("frappe.enqueue"):
			with run_as("Administrator"):
				for role in ("Customer", "Company"):
					signing.finish(self.secrets[role], Client())
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (threads need committed rows)
		with offline_seal(), patch("frappe.enqueue"):
			results = run_together(
				first=lambda: seal_job.run(self.envelope),
				second=lambda: seal_job.run(self.envelope),
			)
		self.assertEqual(results, {"first": None, "second": None})
		frappe.db.rollback()
		doc = frappe.get_doc("Sign Envelope", self.envelope)
		self.assertEqual((doc.status, doc.sealing_state), ("Completed", "Sealed"))
		self.assertEqual(frappe.db.count("Sign Event", {"envelope": self.envelope, "event": "Sealed"}), 1)
		self.assertEqual(frappe.db.count("Sign Event", {"envelope": self.envelope, "event": "Completed"}), 1)
		signed_files = frappe.get_all(
			"File",
			filters={"attached_to_name": self.envelope, "file_name": ["like", "%-signed%"]},
			pluck="name",
		)
		self.assertEqual(signed_files, [doc.signed_file])
		self.assertTrue(audit.verify_chain(self.envelope).ok)

	def purge(self):
		"""Delete everything setUp and the threads committed."""
		frappe.db.rollback()
		envelope = self.envelope
		templates = []
		if envelope:
			version = frappe.db.get_value("Sign Envelope", envelope, "template_version")
			templates = [frappe.db.get_value("Sign Template Version", version, "template")] if version else []
			for doctype in ("Sign Event", "Sign Session", "Sign Capture"):
				frappe.db.delete(doctype, {"envelope": envelope})
			for doctype in ("Sign Envelope Recipient", "Sign Envelope Field"):
				frappe.db.delete(doctype, {"parent": envelope})
			frappe.db.delete("Sign Envelope", {"name": envelope})
			queued = frappe.get_all("Email Queue", filters={"reference_name": envelope}, pluck="name")
			if queued:
				frappe.db.delete("Email Queue Recipient", {"parent": ["in", queued]})
				frappe.db.delete("Email Queue", {"name": ["in", queued]})
			frappe.db.delete("Notification Log", {"document_name": envelope})
			frappe.db.delete("Error Log", {"reference_name": envelope})
		for template in templates:
			frappe.db.delete("Sign Template Version", {"template": template})
			for doctype in ("Sign Template Role", "Sign Template Field"):
				frappe.db.delete(doctype, {"parent": template})
			frappe.db.delete("Sign Template", {"name": template})
		certificate = frappe.db.get_value("Sign Profile", COMPANY, "sealing_certificate")
		frappe.db.delete("Sign Profile", {"name": COMPANY})
		if certificate:
			frappe.db.delete("Sign Certificate", {"name": certificate})
			frappe.db.delete("__Auth", {"doctype": "Sign Certificate", "name": certificate})
		frappe.db.delete("Email Account", {"email_id": "sign-test@example.com"})
		frappe.db.delete("Version", {"creation": [">=", self.started], "ref_doctype": ["like", "Sign %"]})
		for file in frappe.get_all(
			"File", filters={"creation": [">=", self.started]}, fields=["name", "file_url", "is_private"]
		):
			path = (
				get_files_path(file.file_url.rsplit("/", 1)[-1], is_private=file.is_private)
				if file.file_url
				else None
			)
			if path and os.path.exists(path):
				os.remove(path)
			frappe.db.delete("File", {"name": file.name})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (threads need committed rows)
