"""Scheduler, every 15 minutes: expire overdue envelopes, then send due reminders (DESIGN 8)."""

from collections.abc import Callable

import frappe

from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import schedule


def run() -> None:
	for envelope in envelope_service.expiring():
		attempt(envelope_service.expire, envelope)
	for envelope, recipient in schedule.reminders_due():
		attempt(envelope_service.remind, envelope, recipient)


def attempt(action: Callable[..., object], envelope: str, *args: str) -> None:
	"""One envelope per transaction, so a failure never blocks the others (golden rule 11)."""
	try:
		action(envelope, *args)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (scheduler job, transaction boundary)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title="Frappe Sign: scheduler", reference_doctype="Sign Envelope", reference_name=envelope
		)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
