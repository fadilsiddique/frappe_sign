"""Run the template's post-sign action after sealing, as the envelope sender (DESIGN 4.6)."""

import frappe

from frappe_sign.services import actions


def run(envelope: str) -> None:
	try:
		actions.run_post_sign(envelope)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
	except Exception:
		# Only the action rolls back; the signature was committed before. Record and notify
		# (golden rule 11).
		frappe.db.rollback()
		actions.record_failure(envelope)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
