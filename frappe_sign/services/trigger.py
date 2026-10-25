"""Sign Triggers and lifecycle sync through one cached `*` dispatcher (D8, DESIGN 2.4 and 4.7).

dispatch() is the doc_events["*"] handler. For a DocType outside services/gate.py's cached set it
returns after one cache lookup. For the others it does no work in the host transaction beyond
queries: it enqueues jobs with enqueue_after_commit, so nothing runs if the host rolls back.

- Triggers: jobs.triggers.run(trigger, doctype, name), run as the trigger's owner (a Sign Manager,
  who may create envelopes and Sign Trigger Logs). Every run writes a Sign Trigger Log; a failure
  is also commented on the source document.
- Lifecycle: cancel or delete voids the open envelopes; a change while one is open sets
  source_changed and tells the sender; an amendment voids what is still open on the amended
  document. jobs.triggers.lifecycle runs as the envelope's sender.
- The Date event is evaluated by the daily scheduler (P3.2), not here.
"""

from __future__ import annotations

import json
from typing import Any

import frappe
from frappe import _

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import audit, documents, gate, notify
from frappe_sign.services import envelope as envelope_service
from frappe_sign.services.resolvers import resolve_recipients
from frappe_sign.utils.users import run_as

RUN_JOB = "frappe_sign.jobs.triggers.run"
LIFECYCLE_JOB = "frappe_sign.jobs.triggers.lifecycle"
SAVE_METHODS = ("on_update", "on_update_after_submit")
# Fields that change on every save and say nothing about the content.
NOISE_FIELDS = {"modified", "modified_by", "_comments", "_assign", "_liked_by", "_seen", "_user_tags"}
SKIPPED, CREATED, SENT, FAILED, QUEUED = "Skipped", "Created", "Sent", "Failed", "Queued"


def dispatch(doc: Any, method: str | None = None) -> None:
	"""doc_events["*"] handler for after_insert, on_update, on_update_after_submit, on_submit,
	on_cancel and on_trash."""
	flags = frappe.flags
	if flags.in_install or flags.in_migrate or flags.in_patch:
		return
	if doc.doctype not in gate.gated_doctypes():
		return
	sync_lifecycle(doc, method)
	for trigger in matching_triggers(doc, method):
		frappe.enqueue(
			RUN_JOB,
			queue="default",
			enqueue_after_commit=True,
			job_id=f"frappe_sign::trigger::{trigger}::{doc.doctype}::{doc.name}",
			deduplicate=True,
			trigger=trigger,
			doctype=doc.doctype,
			name=doc.name,
		)


# Triggers


def matching_triggers(doc: Any, method: str | None) -> list[str]:
	rows = frappe.get_all(
		"Sign Trigger",
		filters={"reference_doctype": doc.doctype, "enabled": 1, "event": ["!=", "Date"]},
		fields=["name", "event", "workflow_state", "watch_field"],
		order_by="creation asc",
	)
	return [row.name for row in rows if event_matches(row, doc, method)]


def event_matches(trigger: Any, doc: Any, method: str | None) -> bool:
	before = doc.get_doc_before_save() if method != "after_insert" else None
	if trigger.event == "Submit":
		return method == "on_submit"
	if trigger.event == "Save":
		return method == "on_update"
	if method not in (*SAVE_METHODS, "on_submit"):
		return False
	if trigger.event == "Value Change":
		return before is not None and before.get(trigger.watch_field) != doc.get(trigger.watch_field)
	if trigger.event == "Workflow State":
		field = workflow_state_field(doc.doctype)
		return (
			bool(field)
			and doc.get(field) == trigger.workflow_state
			and (not before or before.get(field) != trigger.workflow_state)
		)
	return False


def workflow_state_field(doctype: str) -> str | None:
	from frappe.model.workflow import get_workflow_name

	workflow = get_workflow_name(doctype)
	return frappe.get_cached_value("Workflow", workflow, "workflow_state_field") if workflow else None


def start_log(trigger: str, doctype: str, name: str) -> str:
	"""A Queued Sign Trigger Log, inserted as the trigger's owner."""
	log = frappe.get_doc(
		{
			"doctype": "Sign Trigger Log",
			"trigger": trigger,
			"reference_doctype": doctype,
			"reference_name": name,
			"status": QUEUED,
		}
	).insert()
	return log.name


def run(trigger_name: str, doctype: str, name: str, log: str) -> tuple[str, str | None]:
	"""Body of jobs.triggers.run, as the trigger's owner. Returns the log status and envelope."""
	trigger = frappe.get_doc("Sign Trigger", trigger_name)
	if not trigger.enabled:
		return finish(log, SKIPPED, note=_("The trigger is disabled."))
	if not frappe.db.exists(doctype, name):
		return finish(log, SKIPPED, note=_("{0} {1} no longer exists.").format(_(doctype), name))
	doc = frappe.get_doc(doctype, name)
	if trigger.condition and not frappe.safe_eval(trigger.condition, None, {"doc": doc.as_dict()}):
		return finish(log, SKIPPED, note=_("The condition is false."))
	existing = open_envelope_for(doc, trigger.template)
	if existing:
		return finish(
			log, SKIPPED, existing, note=_("{0} is already open for this document.").format(existing)
		)
	rows = resolve_recipients(trigger.template, doctype, name)
	draft = documents.create_from_document(doc, trigger.template, rows)
	missing = [row["role_label"] for row in rows if row["kind"] != "CC" and not row["resolved"]]
	if trigger.mode == "Send" and not missing:
		envelope_service.send(draft.name)
		return finish(log, SENT, draft.name)
	if missing:
		notify.notify_sender(
			draft,
			_("{0} was created as a draft: add the email of {1} and send it.").format(
				draft.name, ", ".join(missing)
			),
		)
	return finish(log, CREATED, draft.name)


def finish(
	log: str, status: str, envelope: str | None = None, note: str | None = None
) -> tuple[str, str | None]:
	frappe.db.set_value(
		"Sign Trigger Log",
		log,
		{"status": status, "envelope": envelope, "error": note},
		update_modified=False,
	)
	return status, envelope


def open_envelope_for(doc: Any, template: str) -> str | None:
	versions = frappe.get_all("Sign Template Version", filters={"template": template}, pluck="name")
	if not versions:
		return None
	return frappe.db.get_value(
		"Sign Envelope",
		{
			"reference_doctype": doc.doctype,
			"reference_name": doc.name,
			"template_version": ["in", versions],
			"status": ["in", ("Draft", *gate.OPEN)],
		},
		"name",
	)


def record_failure(trigger: str, doctype: str, name: str, log: str | None) -> None:
	"""Called by the job after rolling back a failed run: the log, the Error Log and a comment on
	the source document, so the failure is visible there (D8)."""
	traceback = frappe.get_traceback()
	error = [line for line in traceback.strip().splitlines() if line.strip()][-1:] or [""]
	frappe.log_error(
		title="Frappe Sign: trigger",
		message=f"{trigger} on {doctype} {name}\n\n{traceback}",
		reference_doctype=doctype,
		reference_name=name,
	)
	if log and frappe.db.exists("Sign Trigger Log", log):
		frappe.db.set_value(
			"Sign Trigger Log", log, {"status": FAILED, "error": traceback[-5000:]}, update_modified=False
		)
	if frappe.db.exists(doctype, name):
		frappe.get_doc(doctype, name).add_comment(
			"Info", _("Frappe Sign trigger {0} failed: {1}").format(trigger, error[0][:300])
		)


def trigger_owner(trigger: str) -> str:
	return frappe.db.get_value("Sign Trigger", trigger, "owner") or "Administrator"


# Lifecycle (DESIGN 4.7)


def sync_lifecycle(doc: Any, method: str | None) -> None:
	if method in ("on_cancel", "on_trash"):
		verb = _("cancelled") if method == "on_cancel" else _("deleted")
		reason = _("{0} {1} was {2}.").format(_(doc.doctype), doc.name, verb)
		queue_lifecycle(open_envelopes(doc.doctype, doc.name), "void", reason)
	elif method == "after_insert" and doc.get("amended_from"):
		reason = _("{0} {1} was amended as {2}.").format(_(doc.doctype), doc.amended_from, doc.name)
		queue_lifecycle(open_envelopes(doc.doctype, doc.amended_from), "void", reason)
	elif method in SAVE_METHODS and content_changed(doc):
		queue_lifecycle(open_envelopes(doc.doctype, doc.name), "source_changed", None)


def open_envelopes(doctype: str, name: str) -> list[str]:
	return frappe.get_all(
		"Sign Envelope",
		filters={"reference_doctype": doctype, "reference_name": name, "status": ["in", gate.OPEN]},
		pluck="name",
	)


def content_changed(doc: Any) -> bool:
	before = doc.get_doc_before_save()
	if not before:
		return False
	return comparable(before) != comparable(doc)


def comparable(doc: Any) -> str:
	values = doc.as_dict(no_default_fields=True)
	data = {
		key: value for key, value in values.items() if key not in NOISE_FIELDS and not key.startswith("__")
	}
	for key, value in data.items():
		if isinstance(value, list):
			data[key] = [
				{
					k: v
					for k, v in row.items()
					if k not in NOISE_FIELDS and k not in ("name", "creation", "owner")
				}
				for row in value
			]
	return json.dumps(data, sort_keys=True, default=str)


def queue_lifecycle(envelopes: list[str], action: str, reason: str | None) -> None:
	for envelope in envelopes:
		frappe.enqueue(
			LIFECYCLE_JOB,
			queue="default",
			enqueue_after_commit=True,
			envelope=envelope,
			action=action,
			reason=reason,
		)


def apply_lifecycle(envelope: str, action: str, reason: str | None) -> None:
	"""Body of jobs.triggers.lifecycle, as the envelope's sender."""
	sender = frappe.db.get_value("Sign Envelope", envelope, "sender") or "Administrator"
	with run_as(sender):
		if action == "void":
			void_if_open(envelope, reason or "")
		elif action == "source_changed":
			mark_source_changed(envelope)
		else:
			throw(FieldValidationError, f"Unknown lifecycle action {action}")


def void_if_open(envelope: str, reason: str) -> None:
	doc = frappe.get_doc("Sign Envelope", envelope)
	if doc.status not in gate.OPEN or doc.sealing_state != "Not Started":
		return
	envelope_service.void(envelope, reason)


@audit.retry_on_conflict
def mark_source_changed(envelope: str) -> None:
	doc = envelope_service.locked(envelope)
	if doc.status not in gate.OPEN or doc.source_changed:
		return
	doc.db_set("source_changed", 1)
	audit.append(envelope, "Source Changed", actor="System")
	notify.notify_sender(
		doc,
		_(
			"{0} changed after {1} was sent. Void and resend it so the signers see the current version."
		).format(_(doc.reference_doctype), doc.name),
	)
