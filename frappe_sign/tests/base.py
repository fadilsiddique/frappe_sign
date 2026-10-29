"""Base class for frappe_sign integration tests.

Frappe's IntegrationTestCase rolls back once per class; this one rolls back after every test and
removes the files that tests wrote to disk (a rollback removes File rows, not the files).
"""

import os
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_files_path, now_datetime

from frappe_sign.tests.factories import make_email_account
from frappe_sign.utils.users import run_as


class SignTestCase(IntegrationTestCase):
	needs_email_account = True

	def setUp(self):
		super().setUp()
		self._started = now_datetime()
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		self.addCleanup(self._clean_up)
		if self.needs_email_account:
			make_email_account()
			# ERPNext's setup wizard unsubscribes admin@example.com from all email. Tests send as
			# Administrator and check the mails it gets; the rollback restores the row.
			frappe.db.delete("Email Unsubscribe", {"email": "admin@example.com", "global_unsubscribe": 1})

	def _clean_up(self):
		frappe.set_user("Administrator")  # nosemgrep: frappe-setuser
		remove_files_since(self._started)
		frappe.db.rollback()
		frappe.local.message_log = []

	@contextmanager
	def capture_enqueue(self):
		"""Record frappe.enqueue calls instead of queueing jobs. Yields the list of calls."""
		calls: list[dict] = []

		def record(method, **kwargs):
			calls.append({"method": method, **kwargs})

		with patch("frappe.enqueue", side_effect=record):
			yield calls

	def as_user(self, user: str):
		return run_as(user)

	def refuse_commits(self):
		"""For tests that delete site rows to start from an empty site: any commit, including the
		implicit one before a schema change (frappe.db.sql_ddl), fails the test instead of making the
		deletions permanent."""

		def refuse(*args, **kwargs):
			raise AssertionError("This test deletes site data and must not commit.")

		for method in ("commit", "sql_ddl"):
			patcher = patch.object(frappe.db, method, side_effect=refuse)
			patcher.start()
			self.addCleanup(patcher.stop)


def remove_files_since(started) -> None:
	for file_url, is_private in frappe.get_all(
		"File", filters={"creation": [">=", started]}, fields=["file_url", "is_private"], as_list=True
	):
		if not file_url or not file_url.startswith(("/private/files/", "/files/")):
			continue
		path = get_files_path(file_url.rsplit("/", 1)[-1], is_private=is_private)
		if os.path.exists(path) and not frappe.db.count(
			"File", {"file_url": file_url, "creation": ["<", started]}
		):
			os.remove(path)
