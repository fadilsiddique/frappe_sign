"""Number cards of the Signatures workspace (DESIGN 4.1): awaiting me, awaiting others, completed
this month, expiring in 3 days. Each card opens the Sign Envelope list with its filters."""

from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import get_first_day, today

from frappe_sign.services import envelope as envelope_service
from frappe_sign.utils.dates import after

ROUTE = ["List", "Sign Envelope"]


def card(filters: dict[str, Any]) -> dict[str, Any]:
	return {
		"value": frappe.db.count("Sign Envelope", filters) if filters else 0,
		"fieldtype": "Int",
		"route": ROUTE,
		"route_options": filters,
	}


def awaiting_me() -> dict[str, Any]:
	email = frappe.db.get_value("User", frappe.session.user, "email")
	parents = frappe.get_all(
		"Sign Envelope Recipient",
		filters={"parenttype": "Sign Envelope", "email": email, "status": ["in", envelope_service.WAITING]},
		pluck="parent",
		distinct=True,
	)
	names = frappe.get_list(
		"Sign Envelope",
		filters={"name": ["in", parents or [""]], "status": ["in", envelope_service.OPEN]},
		pluck="name",
	)
	return {**card({"name": ["in", names]} if names else {}), "value": len(names)}


def awaiting_others() -> dict[str, Any]:
	return card({"status": ["in", envelope_service.OPEN], "sender": frappe.session.user})


def completed_this_month() -> dict[str, Any]:
	return card(
		{
			"status": envelope_service.COMPLETED,
			"sender": frappe.session.user,
			"completed_on": [">=", get_first_day(today())],
		}
	)


def expiring_soon() -> dict[str, Any]:
	return card(
		{
			"status": ["in", envelope_service.OPEN],
			"sender": frappe.session.user,
			"expires_on": ["<=", after(days=3)],
		}
	)
