"""Home page data (UX_PLAN "Home", U.3): what waits for the user's signature, the requests the user
sent that wait on others, and the month's figures.

Times go out as seconds ago and dates as plain dates, so the browser's time zone cannot shift them.
Envelopes come through frappe.get_list (the user's permissions); their recipient rows are read for
those envelopes only.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import get_datetime, get_first_day, get_fullname, now_datetime, today

from frappe_sign.services.envelope import COMPLETED, DECLINED, DONE, OPEN, WAITING
from frappe_sign.utils.dates import after

WAITING_LIMIT = 20
SOON_DAYS = 3
RECIPIENT_FIELDS = ["parent", "full_name", "email", "kind", "status", "routing_order", "viewed_on"]


def dashboard() -> dict[str, Any]:
	user = frappe.session.user
	now = now_datetime()
	return {"to_sign": to_sign(user, now), "waiting": waiting(user, now), "month": month(user)}


def to_sign(user: str, now) -> list[dict[str, Any]]:
	email = frappe.db.get_value("User", user, "email")
	mine = frappe.get_all(
		"Sign Envelope Recipient",
		filters={"parenttype": "Sign Envelope", "email": email, "status": ["in", WAITING]},
		fields=["parent", "kind"],
	)
	kinds = {row.parent: row.kind for row in mine}
	envelopes = frappe.get_list(
		"Sign Envelope",
		filters={"status": ["in", OPEN], "name": ["in", list(kinds) or [""]]},
		fields=["name", "title", "sender", "sent_on", "expires_on"],
		order_by="sent_on desc",
	)
	return [
		{
			"name": doc.name,
			"title": doc.title,
			"sender_name": get_fullname(doc.sender) if doc.sender else "",
			"kind": kinds[doc.name],
			"age_seconds": seconds_since(doc.sent_on, now),
			"expires_on": date_only(doc.expires_on),
		}
		for doc in envelopes
	]


def waiting(user: str, now) -> list[dict[str, Any]]:
	envelopes = frappe.get_list(
		"Sign Envelope",
		filters={"status": ["in", OPEN], "sender": user},
		fields=["name", "title", "signing_order", "sent_on", "expires_on"],
		order_by="sent_on desc",
		limit=WAITING_LIMIT,
	)
	rows = frappe.get_all(
		"Sign Envelope Recipient",
		filters={
			"parenttype": "Sign Envelope",
			"parent": ["in", [doc.name for doc in envelopes] or [""]],
			"kind": ["!=", "CC"],
			"status": ["!=", "Delegated"],
		},
		fields=RECIPIENT_FIELDS,
		order_by="routing_order asc, idx asc",
	)
	by_envelope: dict[str, list] = {}
	for row in rows:
		by_envelope.setdefault(row.parent, []).append(row)
	team = colleagues({row.email for row in rows if row.email})
	soon = after(days=SOON_DAYS)
	return [
		waiting_row(doc, by_envelope.get(doc.name, []), team, now, soon) for doc in envelopes
	]


def waiting_row(doc, people: list, team: set[str], now, soon) -> dict[str, Any]:
	nexts = next_people(people, doc.signing_order)
	next_ids = {id(row) for row in nexts}
	return {
		"name": doc.name,
		"title": doc.title,
		# Who to chase: a colleague, or a customer, supplier or other outside person.
		"group": "team" if nexts and all(row.email in team for row in nexts) else "outside",
		"next": [
			{
				"full_name": row.full_name,
				"status": row.status,
				"viewed_seconds": seconds_since(row.viewed_on, now) if row.viewed_on else None,
			}
			for row in nexts
		],
		"people": [
			{"full_name": row.full_name, "kind": row.kind, "status": row.status, "next": id(row) in next_ids}
			for row in people
		],
		"signed": sum(row.status == "Signed" for row in people),
		"total": len(people),
		"sent_seconds": seconds_since(doc.sent_on, now),
		"expires_on": date_only(doc.expires_on),
		"expiring_soon": bool(doc.expires_on) and get_datetime(doc.expires_on) <= soon,
	}


def next_people(people: list, signing_order: str | None) -> list:
	"""Who the request waits on: every unsigned person at once, or the lowest order still open."""
	open_rows = [row for row in people if row.status not in DONE]
	if signing_order == "Parallel" or not open_rows:
		return open_rows
	first = min(row.routing_order for row in open_rows)
	return [row for row in open_rows if row.routing_order == first]


def colleagues(emails: set[str]) -> set[str]:
	"""Emails of enabled Desk users: people on the user's own team."""
	if not emails:
		return set()
	return set(
		frappe.get_all(
			"User",
			filters={"email": ["in", list(emails)], "enabled": 1, "user_type": "System User"},
			pluck="email",
		)
	)


def month(user: str) -> dict[str, int]:
	start = get_first_day(today())
	return {
		"completed": frappe.db.count(
			"Sign Envelope", {"status": COMPLETED, "sender": user, "completed_on": [">=", start]}
		),
		"waiting": frappe.db.count("Sign Envelope", {"status": ["in", OPEN], "sender": user}),
		"declined": frappe.db.count(
			"Sign Envelope", {"status": DECLINED, "sender": user, "modified": [">=", start]}
		),
	}


def seconds_since(moment, now) -> int:
	return max(0, int((now - get_datetime(moment)).total_seconds())) if moment else 0


def date_only(moment) -> str | None:
	return str(get_datetime(moment).date()) if moment else None
