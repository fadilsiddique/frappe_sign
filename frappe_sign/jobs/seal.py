"""Seal a completed envelope, deduplicated by job_id (queue: long). DESIGN 5.4."""

import frappe

from frappe_sign.services import sealing


def run(envelope: str) -> None:
	# Queued -> Sealing is committed on its own, so a second job sees it and stops.
	started = sealing.begin(envelope)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
	if not started:
		return
	try:
		sealing.run(envelope)
		frappe.db.commit()
	except Exception as error:
		# Record the attempt and schedule the retry (golden rule 11).
		frappe.db.rollback()
		sealing.fail(envelope, str(error))
		frappe.db.commit()


def retry_due() -> None:
	"""Scheduler, every minute: queue failed seals whose backoff has passed."""
	sealing.retry_due()
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (scheduler job, transaction boundary)
