"""Run one domain event handler in its own job and commit (D17)."""

import frappe

from frappe_sign.services import events


def run(handler: str, domain_event: str, envelope: str) -> None:
	try:
		events.run_handler(handler, domain_event, envelope)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
	except Exception:
		# Only this handler's writes roll back; the change that published the event is already
		# committed. Record it in the Error Log (golden rule 11).
		frappe.db.rollback()
		events.record_failure(handler, domain_event, envelope)
		frappe.db.commit()
