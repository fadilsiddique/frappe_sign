"""services/audit.py (P1.6): the hash-chained audit log (DESIGN 5.5)."""

import hashlib
import json
from itertools import pairwise
from unittest.mock import patch

import frappe
from frappe.utils import set_request

from frappe_sign.services import audit
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_envelope
from frappe_sign.utils.dates import utc_now
from frappe_sign.utils.request import Client


def expected_hash(row: dict) -> str:
	"""DESIGN 5.5, written out independently of the code under test."""
	payload = json.loads(row["payload"]) if row["payload"] else None
	event = {
		"envelope": row["envelope"],
		"seq": row["seq"],
		"recipient_row": row["recipient_row"] or None,
		"event": row["event"],
		"at": row["at"].strftime("%Y-%m-%dT%H:%M:%S.%f"),
		"actor": row["actor"] or None,
		"ip": row["ip"] or None,
		"user_agent": row["user_agent"] or None,
		"payload": payload,
	}
	canonical = json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
	return hashlib.sha256((row["prev_hash"] + canonical).encode()).hexdigest()


class TestAuditChain(SignTestCase):
	def setUp(self):
		super().setUp()
		self.envelope = make_envelope().name

	def rows(self) -> list[dict]:
		return frappe.get_all(
			"Sign Event",
			filters={"envelope": self.envelope},
			fields=["name", *audit.HASHED_FIELDS, "prev_hash", "hash"],
			order_by="seq asc",
		)

	def append_three(self):
		audit.append(self.envelope, "Created")
		audit.append(
			self.envelope,
			"Viewed",
			recipient_row="row-1",
			actor="signer@example.com",
			client=Client(ip="203.0.113.9", user_agent="Mozilla/5.0 (iPhone)"),
		)
		audit.append(self.envelope, "Signed", payload={"intermediate_sha256": "a" * 64, "kind": "Signer"})

	def test_events_chain_from_the_envelope_name(self):
		self.append_three()
		rows = self.rows()
		self.assertEqual([row.seq for row in rows], [1, 2, 3])
		self.assertEqual(rows[0].prev_hash, hashlib.sha256(self.envelope.encode()).hexdigest())
		for previous, row in pairwise(rows):
			self.assertEqual(row.prev_hash, previous.hash)
		for row in rows:
			self.assertEqual(row.hash, expected_hash(row))

	def test_at_is_utc_with_microseconds(self):
		event = audit.append(self.envelope, "Created")
		self.assertLess(abs((utc_now() - event.at).total_seconds()), 60)
		stored = frappe.db.get_value("Sign Event", event.name, "at")
		self.assertEqual(stored, event.at)

	def test_actor_ip_and_user_agent_default_to_the_request(self):
		set_request(method="POST", path="/api/method/x", headers={"User-Agent": "TestAgent/1.0"})
		frappe.local.request_ip = "198.51.100.4"
		try:
			event = audit.append(self.envelope, "Created")
		finally:
			frappe.local.request = None
			frappe.local.request_ip = None
		self.assertEqual(
			(event.actor, event.ip, event.user_agent), ("Administrator", "198.51.100.4", "TestAgent/1.0")
		)

	def test_seq_is_assigned_under_the_envelope_row_lock(self):
		with patch.object(audit, "lock_envelope", wraps=audit.lock_envelope) as lock:
			audit.append(self.envelope, "Created")
		lock.assert_called_once_with(self.envelope)
		queries = []
		original = frappe.db.sql

		def spy(query, *args, **kwargs):
			queries.append(str(query).lower())
			return original(query, *args, **kwargs)

		with patch.object(frappe.db, "sql", side_effect=spy):
			audit.lock_envelope(self.envelope)
		self.assertTrue(any("for update" in query for query in queries), queries)

	def test_unknown_envelope(self):
		self.assertRaises(frappe.DoesNotExistError, audit.append, "SIGN-NOPE-00001", "Created")

	def test_verify_good_chain(self):
		self.append_three()
		report = audit.verify_chain(self.envelope)
		self.assertTrue(report.ok, report)
		self.assertEqual(report.count, 3)
		self.assertEqual(report.head, self.rows()[-1].hash)
		self.assertIsNone(report.first_bad_seq)

	def test_empty_chain_is_ok(self):
		report = audit.verify_chain(self.envelope)
		self.assertTrue(report.ok)
		self.assertEqual(report.count, 0)

	def test_tampered_field_is_found(self):
		self.append_three()
		rows = self.rows()
		frappe.db.set_value(
			"Sign Event", rows[1].name, "actor", "someone-else@example.com", update_modified=False
		)
		report = audit.verify_chain(self.envelope)
		self.assertFalse(report.ok)
		self.assertEqual(report.first_bad_seq, 2)
		self.assertIn("hash", report.reason)

	def test_tampered_payload_is_found(self):
		self.append_three()
		rows = self.rows()
		frappe.db.set_value(
			"Sign Event", rows[2].name, "payload", json.dumps({"kind": "Signer"}), update_modified=False
		)
		self.assertEqual(audit.verify_chain(self.envelope).first_bad_seq, 3)

	def test_rewritten_event_with_fresh_hash_breaks_the_next_link(self):
		self.append_three()
		rows = self.rows()
		forged = {**rows[0], "actor": "forger@example.com"}
		frappe.db.set_value(
			"Sign Event",
			rows[0].name,
			{"actor": forged["actor"], "hash": expected_hash(forged)},
			update_modified=False,
		)
		report = audit.verify_chain(self.envelope)
		self.assertEqual(report.first_bad_seq, 2)
		self.assertIn("prev_hash", report.reason)

	def test_deleted_event_is_found(self):
		self.append_three()
		frappe.db.delete("Sign Event", {"name": self.rows()[1].name})
		report = audit.verify_chain(self.envelope)
		self.assertEqual(report.first_bad_seq, 2)
		self.assertIn("missing", report.reason)

	def test_forked_seq_is_refused_by_the_database(self):
		audit.append(self.envelope, "Created")
		row = self.rows()[0]
		duplicate = frappe.get_doc(
			{
				"doctype": "Sign Event",
				"envelope": self.envelope,
				"seq": 1,
				"event": "Viewed",
				"at": row.at,
				"prev_hash": row.prev_hash,
				"hash": row.hash,
			}
		)
		self.assertRaises(frappe.UniqueValidationError, duplicate.insert)


class TestRetryOnConflict(SignTestCase):
	def test_retries_after_a_snapshot_conflict(self):
		calls = []

		@audit.retry_on_conflict
		def flaky():
			calls.append(1)
			if len(calls) == 1:
				raise frappe.QueryDeadlockError("1020")
			return "done"

		with patch.object(frappe.db, "rollback") as rollback:
			self.assertEqual(flaky(), "done")
		self.assertEqual((len(calls), rollback.call_count), (2, 1))

	def test_gives_up_after_three_attempts(self):
		@audit.retry_on_conflict
		def always():
			raise frappe.QueryDeadlockError("1020")

		with patch.object(frappe.db, "rollback"), self.assertRaises(frappe.QueryDeadlockError):
			always()
