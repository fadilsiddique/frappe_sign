"""The Sent list (UX_PLAN "Sent", U.4): requests under the user's permissions, with tabs, counts,
search, filters and paging. Rows share their shape with Home's "Waiting on others"
(services/home.py), plus status, source document and sender.

The date filters use the day a request was made, so drafts can be found too.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any

import frappe
from frappe.utils import get_fullname, now_datetime

from frappe_sign.services import home
from frappe_sign.services.envelope import COMPLETED, DECLINED, EXPIRED, OPEN, VOIDED
from frappe_sign.utils.boot import STAFF_ROLES
from frappe_sign.utils.dates import after

TABS: dict[str, tuple[str, ...]] = {
	"open": ("Draft", *OPEN),
	"completed": (COMPLETED,),
	"closed": (DECLINED, VOIDED, EXPIRED),
}
PAGE = 50
FIELDS = [
	"name",
	"title",
	"status",
	"send_state",
	"sealing_state",
	"sender",
	"signing_order",
	"reference_doctype",
	"reference_name",
	"sent_on",
	"expires_on",
]


def list_requests(
	status: str = "open",
	search: str | None = None,
	reference_doctype: str | None = None,
	sender: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
	start: int = 0,
	limit: int = PAGE,
) -> dict[str, Any]:
	frappe.only_for(list(STAFF_ROLES))
	limit = max(1, min(int(limit), 200))
	options = dict(
		search=search,
		reference_doctype=reference_doctype,
		sender=sender,
		date_from=date_from,
		date_to=date_to,
	)
	# One extra row tells whether there is another page.
	envelopes = frappe.get_list(
		"Sign Envelope",
		**query(status, **options),
		fields=FIELDS,
		order_by="modified desc, name desc",
		start=max(0, int(start)),
		page_length=limit + 1,
	)
	has_more = len(envelopes) > limit
	envelopes = envelopes[:limit]
	people, team = home.load_people([doc.name for doc in envelopes])
	now, soon = now_datetime(), after(days=home.SOON_DAYS)
	return {
		"rows": [request_row(doc, people.get(doc.name, []), team, now, soon) for doc in envelopes],
		"has_more": has_more,
	}


def request_counts(
	search: str | None = None,
	reference_doctype: str | None = None,
	sender: str | None = None,
	date_from: str | None = None,
	date_to: str | None = None,
) -> dict[str, int]:
	"""How many requests each tab holds under the same filters (the tab itself does not filter)."""
	frappe.only_for(list(STAFF_ROLES))
	statuses = frappe.get_list(
		"Sign Envelope",
		**query(
			"all",
			search=search,
			reference_doctype=reference_doctype,
			sender=sender,
			date_from=date_from,
			date_to=date_to,
		),
		pluck="status",
	)
	by_status = Counter(statuses)
	counts = {
		tab: sum(by_status[status] for status in statuses_in_tab) for tab, statuses_in_tab in TABS.items()
	}
	return {**counts, "all": len(statuses)}


def filter_options() -> dict[str, Any]:
	"""What the Filter menu offers: the source DocTypes and the senders among the requests the user may see."""
	frappe.only_for(list(STAFF_ROLES))
	rows = frappe.get_list("Sign Envelope", fields=["reference_doctype", "sender"], limit=5000)
	senders = sorted({row.sender for row in rows if row.sender})
	return {
		"doctypes": sorted({row.reference_doctype for row in rows if row.reference_doctype}),
		"senders": [{"name": name, "full_name": get_fullname(name)} for name in senders],
	}


def query(status: str, **options: str | None) -> dict[str, Any]:
	filters: list[list[Any]] = []
	if status in TABS:
		filters.append(["status", "in", list(TABS[status])])
	if options["reference_doctype"]:
		filters.append(["reference_doctype", "=", options["reference_doctype"]])
	if options["sender"]:
		filters.append(["sender", "=", options["sender"]])
	if options["date_from"]:
		filters.append(["creation", ">=", f"{options['date_from']} 00:00:00"])
	if options["date_to"]:
		filters.append(["creation", "<=", f"{options['date_to']} 23:59:59"])
	return {"filters": filters, "or_filters": search_filters(options["search"])}


def search_filters(search: str | None) -> list[list[Any]]:
	text = (search or "").strip()[:100]
	if not text:
		return []
	# frappe leaves a value that holds a % as it is, so the wildcards are added here and the
	# user's own % and _ are escaped.
	pattern = "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
	people = frappe.get_all(
		"Sign Envelope Recipient",
		filters={"parenttype": "Sign Envelope"},
		or_filters=[["full_name", "like", pattern], ["email", "like", pattern]],
		pluck="parent",
		limit=500,
	)
	return [
		["title", "like", pattern],
		["reference_name", "like", pattern],
		["name", "in", people or [""]],
	]


def request_row(doc: Any, people: list[Any], team: set[str], now: datetime, soon: datetime) -> dict[str, Any]:
	row = home.waiting_row(doc, people, team, now, soon)
	row.update(
		status=doc.status,
		send_state=doc.send_state,
		sealing_state=doc.sealing_state,
		reference_doctype=doc.reference_doctype,
		reference_name=doc.reference_name,
		sender=doc.sender,
		sender_name=get_fullname(doc.sender) if doc.sender else "",
		sent_seconds=home.seconds_since(doc.sent_on, now) if doc.sent_on else None,
	)
	if doc.status == "Draft":
		row.update(group="draft", next=[], expiring_soon=False)
	elif doc.status not in OPEN:
		# Nobody is left to chase: finished or closed.
		group = "done" if doc.status == COMPLETED else "closed"
		row.update(group=group, next=[], expiring_soon=False)
		row["people"] = [{**person, "next": False} for person in row["people"]]
	return row
