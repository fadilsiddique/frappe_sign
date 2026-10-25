"""Bulk send from the list view (queue: long): one envelope per document, each in its own commit."""

import frappe

from frappe_sign.services import documents


def run(doctype: str, names: list[str], template: str) -> None:
	sent: list[str] = []
	failed: dict[str, str] = {}
	for name in names:
		try:
			documents.send_resolved(doctype, name, template)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit (jobs are transaction boundaries)
			sent.append(name)
		except Exception as error:
			# One document's failure must not stop the others; record it (golden rule 11).
			frappe.db.rollback()
			failed[name] = str(error)[:200] or type(error).__name__
			frappe.log_error(title="Frappe Sign: bulk send", reference_doctype=doctype, reference_name=name)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
	documents.report_bulk(doctype, sent, failed)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit
