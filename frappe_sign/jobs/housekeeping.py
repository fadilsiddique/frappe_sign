"""Scheduler, daily: certificate expiry warnings, session purge and date triggers (DESIGN 8)."""

import frappe

from frappe_sign.services import schedule

STEPS = ("warn_certificate_expiry", "purge_sessions", "run_date_triggers")


def run() -> None:
	for step in STEPS:
		try:
			getattr(schedule, step)()
			frappe.db.commit()  # nosemgrep: frappe-manual-commit (scheduler job, transaction boundary)
		except Exception:
			# A failing step must not skip the others; record it (golden rule 11).
			frappe.db.rollback()
			frappe.log_error(title=f"Frappe Sign: scheduler {step}")
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
