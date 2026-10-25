"""Render and send: freeze the PDF, issue tokens, set Sent (queue: default)."""

import frappe

from frappe_sign.services import envelope as envelope_service


def run(envelope: str) -> None:
	try:
		envelope_service.render_and_send(envelope)
		frappe.db.commit()
	except envelope_service.SendFailed as error:
		frappe.db.rollback()
		envelope_service.mark_send_failed(envelope, str(error))
		frappe.db.commit()
	except Exception:
		# Record and notify; the envelope must not stay Queued forever (golden rule 11).
		frappe.db.rollback()
		envelope_service.record_send_crash(envelope)
		frappe.db.commit()
