"""Hash-chained audit log: append Sign Events under the envelope row lock, verify the chain (DESIGN 5.5).

hash = sha256(prev_hash + canonical_json(event)). The first event's prev_hash is
sha256(envelope name). Canonical JSON has sorted keys, no whitespace and the UTC timestamp with
microseconds. Only HASHED_FIELDS are hashed; Frappe metadata and the hash fields are not.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any

import frappe

from frappe_sign.utils.dates import utc_now
from frappe_sign.utils.hashing import sha256_hex
from frappe_sign.utils.request import Client, current_client

HASHED_FIELDS = ("envelope", "seq", "recipient_row", "event", "at", "actor", "ip", "user_agent", "payload")


@dataclass(frozen=True)
class ChainReport:
	ok: bool
	count: int
	head: str | None
	first_bad_seq: int | None = None
	reason: str | None = None


LOCK_ATTEMPTS = 3


def retry_on_conflict[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
	"""Retry a service entry point whose envelope row lock hit a snapshot conflict.

	MariaDB 11.8 (innodb_snapshot_isolation) refuses SELECT ... FOR UPDATE on a row that another
	transaction changed after this one's first read, and Frappe raises QueryDeadlockError. When two
	signers finish together, the second must wait and then see the first one's work, so the call is
	rolled back and run again with a fresh read view. Use it only on functions that start the
	transaction's work (an API call or job step), never on helpers called inside one.
	"""

	@wraps(fn)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
		for attempt in range(1, LOCK_ATTEMPTS + 1):
			try:
				return fn(*args, **kwargs)
			except frappe.QueryDeadlockError:
				if attempt == LOCK_ATTEMPTS:
					raise
				frappe.db.rollback()
		raise AssertionError("unreachable")

	return wrapper


def lock_envelope(envelope: str) -> None:
	"""SELECT ... FOR UPDATE on the envelope row; held until the transaction ends."""
	found = frappe.db.sql("select name from `tabSign Envelope` where name = %s for update", envelope)
	if not found:
		raise frappe.DoesNotExistError(f"Sign Envelope {envelope} not found")


def append(
	envelope: str,
	event: str,
	*,
	recipient_row: str | None = None,
	actor: str | None = None,
	payload: dict[str, Any] | None = None,
	client: Client | None = None,
) -> Any:
	"""Insert the next Sign Event. The caller has already checked access to the envelope."""
	lock_envelope(envelope)
	client = client or current_client()
	last = frappe.db.get_value(
		"Sign Event", {"envelope": envelope}, ["seq", "hash"], order_by="seq desc", as_dict=True
	)
	values: dict[str, Any] = {
		"envelope": envelope,
		"seq": (last.seq if last else 0) + 1,
		"recipient_row": recipient_row or None,
		"event": event,
		"at": utc_now(),
		"actor": actor or frappe.session.user,
		"ip": client.ip or None,
		"user_agent": client.user_agent or None,
		"payload": payload or None,
	}
	prev_hash = last.hash if last else genesis(envelope)
	doc = frappe.get_doc(
		{
			"doctype": "Sign Event",
			**values,
			"payload": canonical_json(values["payload"]) if values["payload"] else None,
			"prev_hash": prev_hash,
			"hash": event_hash(prev_hash, values),
		}
	)
	# No role may create Sign Events (DESIGN 2.6); the calling service checked envelope access first.
	doc.insert(ignore_permissions=True)
	return doc


def genesis(envelope: str) -> str:
	return sha256_hex(envelope)


def canonical_json(value: Any) -> str:
	return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def event_hash(prev_hash: str, values: dict[str, Any]) -> str:
	at: datetime = values["at"]
	event = {field: values.get(field) for field in HASHED_FIELDS}
	event["at"] = at.strftime("%Y-%m-%dT%H:%M:%S.%f")
	return sha256_hex(prev_hash + canonical_json(event))


def head(envelope: str) -> str | None:
	value = frappe.db.get_value("Sign Event", {"envelope": envelope}, "hash", order_by="seq desc")
	return str(value) if value else None


def verify_chain(envelope: str) -> ChainReport:
	"""Recompute every link and report the first event that does not match."""
	rows = frappe.get_all(
		"Sign Event",
		filters={"envelope": envelope},
		fields=[*HASHED_FIELDS, "prev_hash", "hash"],
		order_by="seq asc",
	)
	prev_hash = genesis(envelope)
	for expected_seq, row in enumerate(rows, start=1):
		problem = link_problem(row, expected_seq, prev_hash)
		if problem:
			return ChainReport(False, len(rows), rows[-1].hash, first_bad_seq=expected_seq, reason=problem)
		prev_hash = row.hash
	return ChainReport(True, len(rows), rows[-1].hash if rows else None)


def link_problem(row: Any, expected_seq: int, prev_hash: str) -> str | None:
	if row.seq != expected_seq:
		return f"event {expected_seq} is missing (found seq {row.seq})"
	if row.prev_hash != prev_hash:
		return "prev_hash does not match the previous event's hash"
	values = {field: row.get(field) or None for field in HASHED_FIELDS}
	values["seq"] = row.seq
	values["payload"] = json.loads(row.payload) if row.payload else None
	if event_hash(prev_hash, values) != row.hash:
		return "hash does not match the event's contents"
	return None
