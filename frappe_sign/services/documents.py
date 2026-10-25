"""Send a document for signature from its Desk form, print view or list view (DESIGN 4.1).

The Desk dialog lists the published templates for the DocType, fills recipients from the resolvers
(services/resolvers.py) and sends with one call. The print view passes the Print Format and
Letter Head it shows. A bulk send from the list view runs in jobs.bulk.run, one envelope per
document, with recipients taken from the resolvers only.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import notify
from frappe_sign.services.resolvers import primary_party, resolve_recipients

BULK_JOB = "frappe_sign.jobs.bulk.run"
BULK_LIMIT = 100


def templates_for(doctype: str) -> list[dict[str, Any]]:
	"""Published, active templates for a DocType; the Sign Settings default comes first."""
	frappe.has_permission("Sign Template", "read", throw=True)
	default = frappe.db.get_value(
		"Sign Enabled DocType", {"parent": "Sign Settings", "reference_doctype": doctype}, "default_template"
	)
	rows = frappe.get_list(
		"Sign Template",
		filters={"reference_doctype": doctype, "is_active": 1, "published_version": ["is", "set"]},
		fields=["name", "title", "print_format", "letter_head", "source_type"],
		order_by="title asc",
	)
	for row in rows:
		row["is_default"] = int(row.name == default)
	return sorted(rows, key=lambda row: -row["is_default"])


def send_from_document(
	doctype: str,
	name: str,
	template: str,
	recipients: list[dict[str, Any]],
	*,
	message: str | None = None,
	print_format: str | None = None,
	letter_head: str | None = None,
) -> str:
	"""Create an envelope for the document from the template and send it. Returns its name."""
	source = frappe.get_doc(doctype, name)
	source.check_permission("print")
	draft = create_from_document(source, template, recipients, message, print_format, letter_head)
	envelope_service.send(draft.name)
	return draft.name


def create_from_document(
	source: Any,
	template: str,
	recipients: list[dict[str, Any]],
	message: str | None = None,
	print_format: str | None = None,
	letter_head: str | None = None,
) -> Any:
	values = frappe.db.get_value(
		"Sign Template",
		template,
		["published_version", "reference_doctype", "title", "company"],
		as_dict=True,
	)
	if not values or not values.published_version:
		throw(FieldValidationError, _("Template {0} has no published version.").format(template))
	if values.reference_doctype and values.reference_doctype != source.doctype:
		throw(
			FieldValidationError,
			_("Template {0} is for {1}, not {2}.").format(template, values.reference_doctype, source.doctype),
		)
	party_type, party = primary_party(recipients)
	return envelope_service.create_draft(
		{
			"template_version": values.published_version,
			"title": f"{_(source.doctype)} {source.name}",
			"company": source.get("company") or values.company,
			"message": message,
			"reference_doctype": source.doctype,
			"reference_name": source.name,
			"party_type": party_type,
			"party": party,
			"print_format": print_format,
			"letter_head": letter_head,
			"recipients": recipients,
		}
	)


def send_resolved(doctype: str, name: str, template: str) -> str:
	"""Send with the resolvers' recipients only. Fails when a Signer or Approver has no email."""
	rows = resolve_recipients(template, doctype, name)
	missing = [row["role_label"] for row in rows if row["kind"] != "CC" and not row["resolved"]]
	if missing:
		throw(
			FieldValidationError,
			_("No email address found for {0} on {1} {2}.").format(", ".join(missing), _(doctype), name),
		)
	return send_from_document(doctype, name, template, rows)


def queue_bulk_send(doctype: str, names: list[str], template: str) -> int:
	"""Check access and queue jobs.bulk.run for the selected documents."""
	frappe.has_permission("Sign Envelope", "create", throw=True)
	frappe.has_permission("Sign Template", "read", doc=template, throw=True)
	names = list(dict.fromkeys(names or []))
	if not names:
		throw(FieldValidationError, _("Select at least one document."))
	if len(names) > BULK_LIMIT:
		throw(FieldValidationError, _("Send at most {0} documents at a time.").format(BULK_LIMIT))
	frappe.enqueue(
		BULK_JOB,
		queue="long",
		timeout=3600,
		enqueue_after_commit=True,
		doctype=doctype,
		names=names,
		template=template,
	)
	return len(names)


def report_bulk(doctype: str, sent: list[str], failed: dict[str, str]) -> None:
	"""Tell the user who started a bulk send what happened; failures are in the Error Log."""
	subject = _("Send for signature: {0} of {1} {2} sent").format(
		len(sent), len(sent) + len(failed), _(doctype)
	)
	if failed:
		subject += ". " + _("Not sent: {0}").format(
			", ".join(f"{name} ({reason})" for name, reason in failed.items())
		)
	notify.notify_user(frappe.session.user, subject[:1000], doctype)
