"""Run Sign Trigger work and lifecycle sync after the source document commits (D8)."""

import frappe

from frappe_sign.services import trigger as trigger_service
from frappe_sign.utils.users import run_as


def run(trigger: str, doctype: str, name: str) -> None:
	"""One Sign Trigger run, as the trigger's owner. Every run leaves a Sign Trigger Log."""
	log = None
	with run_as(trigger_service.trigger_owner(trigger)):
		try:
			log = trigger_service.start_log(trigger, doctype, name)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
			trigger_service.run(trigger, doctype, name, log)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
		except Exception:
			# Record in the log, the Error Log and on the source document (golden rule 11).
			frappe.db.rollback()
			trigger_service.record_failure(trigger, doctype, name, log)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit


def lifecycle(envelope: str, action: str, reason: str | None = None) -> None:
	"""Void an open envelope or flag source_changed, as the envelope's sender."""
	try:
		trigger_service.apply_lifecycle(envelope, action, reason)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
	except Exception:
		frappe.db.rollback()
		frappe.log_error(
			title="Frappe Sign: lifecycle", reference_doctype="Sign Envelope", reference_name=envelope
		)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
