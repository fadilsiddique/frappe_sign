"""Bulk send from the list view (queue: long): one envelope per document, each in its own commit."""

import frappe

from frappe_sign.services import documents


def run(run: str) -> None:
	"""Work through a Sign Bulk Run as the user who started it, reporting progress in realtime."""
	doc = documents.start_bulk(run)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
	if not doc:
		return
	for item in doc.items:
		envelope, error = send_one(doc, item)
		message = documents.record_bulk_item(doc, item, envelope, error)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		publish(doc, message)
	message = documents.finish_bulk(doc)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
	publish(doc, message)


def send_one(doc, item) -> tuple[str | None, str | None]:
	try:
		return documents.send_resolved(doc.reference_doctype, item.document, doc.template), None
	except Exception as error:
		# One document's failure must not stop the others; record it (golden rule 11).
		frappe.db.rollback()
		frappe.log_error(
			title="Frappe Sign: bulk send",
			reference_doctype=doc.reference_doctype,
			reference_name=item.document,
		)
		return None, str(error)[:200] or type(error).__name__


def publish(doc, message: dict) -> None:
	frappe.publish_realtime("frappe_sign_bulk", message, user=doc.owner)
