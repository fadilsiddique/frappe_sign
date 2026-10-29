"""What the scheduler does (DESIGN 8): reminders, certificate warnings, session purge, date triggers.

These functions only decide and write; jobs/reminders.py and jobs/housekeeping.py own the
transactions. Every query takes "now" from the clock, so tests freeze time.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, cint, getdate, now_datetime

from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import notify, settings, trigger
from frappe_sign.utils.dates import utc_now

# Days before a seal certificate ends at which Sign Managers are warned; 0 is "has ended".
WARNING_BANDS = (30, 14, 7, 1, 0)
SESSION_KEEP_DAYS = 1
DATE_CATCH_UP_DAYS = 3
MANAGER_ROLES = ("Sign Manager", "System Manager")
SIGNER_EVENTS = ("Delivered", "Reminded")


def reminders_due() -> list[tuple[str, str]]:
	"""(envelope, recipient row) pairs that have waited `default_reminder_days` since their last link."""
	days = settings.reminder_days()
	if days <= 0:
		return []
	names = frappe.get_all(
		"Sign Envelope",
		filters={
			"status": ["in", envelope_service.OPEN],
			"sealing_state": "Not Started",
			"expires_on": [">", now_datetime()],
		},
		pluck="name",
	)
	if not names:
		return []
	# Ordered by time, so the dict keeps each recipient's latest link event.
	last_link = dict(
		frappe.get_all(
			"Sign Event",
			filters={"envelope": ["in", names], "event": ["in", SIGNER_EVENTS]},
			fields=["recipient_row", "at"],
			order_by="at asc",
			as_list=True,
		)
	)
	limit = utc_now() - timedelta(days=days)
	waiting = frappe.get_all(
		"Sign Envelope Recipient",
		filters={"parent": ["in", names], "status": ["in", envelope_service.WAITING]},
		fields=["parent", "name", "kind"],
		order_by="parent, idx",
	)
	return [
		(row.parent, row.name)
		for row in waiting
		if row.kind in envelope_service.SIGNING_KINDS
		and (last := last_link.get(row.name)) is not None
		and last <= limit
	]


def warn_certificate_expiry() -> list[str]:
	"""Warn Sign Managers once per band as a seal certificate nears its end. Returns the certificates."""
	warned = []
	for certificate in frappe.get_all(
		"Sign Certificate", filters={"valid_to": ["is", "set"]}, fields=["name", "title", "valid_to"]
	):
		band = warning_band(certificate.valid_to)
		if band is None or already_warned(certificate.name, band):
			continue
		text = band_text(certificate.title, certificate.valid_to, band)
		frappe.get_doc("Sign Certificate", certificate.name).add_comment("Info", text)
		for user in sign_managers():
			notify.notify_user(user, text)
		warned.append(certificate.name)
	return warned


def warning_band(valid_to: datetime) -> int | None:
	days_left = (valid_to - now_datetime()).days
	return next((band for band in sorted(WARNING_BANDS) if days_left <= band), None)


def band_marker(band: int) -> str:
	return f"[expiry band {band}]"


def already_warned(certificate: str, band: int) -> bool:
	return bool(
		frappe.db.exists(
			"Comment",
			{
				"reference_doctype": "Sign Certificate",
				"reference_name": certificate,
				"content": ["like", f"%{band_marker(band)}%"],
			},
		)
	)


def band_text(title: str, valid_to: datetime, band: int) -> str:
	if band == 0:
		text = _("The seal certificate {0} has ended. New documents cannot be sealed.").format(title)
	else:
		text = _("The seal certificate {0} ends on {1}. Get a new one before then.").format(
			title, getdate(valid_to)
		)
	return f"{text} {band_marker(band)}"


def sign_managers() -> list[str]:
	users = frappe.get_all(
		"Has Role", filters={"role": ["in", MANAGER_ROLES], "parenttype": "User"}, pluck="parent"
	)
	enabled = frappe.get_all("User", filters={"name": ["in", list(set(users))], "enabled": 1}, pluck="name")
	return [user for user in enabled if user not in ("Administrator", "Guest")]


def purge_sessions() -> int:
	"""Delete Sign Sessions that ended more than a day ago. The audit trail keeps what they did."""
	filters = {"expires_on": ["<", now_datetime() - timedelta(days=SESSION_KEEP_DAYS)]}
	count = frappe.db.count("Sign Session", filters)
	if count:
		frappe.db.delete("Sign Session", filters)
	return count


def run_date_triggers() -> int:
	"""Queue a Sign Trigger run for each document whose date plus the offset is today.

	The window reaches back DATE_CATCH_UP_DAYS, so a day the scheduler missed is caught up on. A
	document that already has a Sign Trigger Log for the trigger never runs again.
	"""
	queued = 0
	for row in frappe.get_all(
		"Sign Trigger",
		filters={"event": "Date", "enabled": 1},
		fields=["name", "reference_doctype", "date_field", "days_offset"],
	):
		queued += queue_date_trigger(row)
	return queued


def queue_date_trigger(row: Any) -> int:
	if not row.date_field:
		return 0
	offset = cint(row.days_offset)
	today = getdate()
	window = [add_days(today, -offset - DATE_CATCH_UP_DAYS), add_days(today, -offset)]
	filters: dict[str, Any] = {row.date_field: ["between", window]}
	if frappe.get_meta(row.reference_doctype).is_submittable:
		filters["docstatus"] = ["!=", 2]
	names = frappe.get_all(row.reference_doctype, filters=filters, pluck="name")
	done = set(
		frappe.get_all(
			"Sign Trigger Log",
			filters={
				"trigger": row.name,
				"reference_doctype": row.reference_doctype,
				"reference_name": ["in", names],
			},
			pluck="reference_name",
		)
	)
	pending = [name for name in names if name not in done]
	for name in pending:
		frappe.enqueue(
			trigger.RUN_JOB,
			queue="default",
			enqueue_after_commit=True,
			job_id=f"frappe_sign::date::{row.name}::{row.reference_doctype}::{name}",
			deduplicate=True,
			trigger=row.name,
			doctype=row.reference_doctype,
			name=name,
		)
	return len(pending)
