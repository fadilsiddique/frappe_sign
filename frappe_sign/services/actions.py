"""Post-sign actions, run as the envelope sender (DESIGN 4.6).

queue_post_sign (an envelope_completed handler) queues jobs.actions.run when the envelope's
template version has an action. The job calls run_post_sign as the sender, so the sender's
permissions apply, and commits. A failure rolls back the action only: the signature and the sealed
PDF were committed before. record_failure then writes the Error Log, a "Post-Sign Action" Sign
Event with the error and a notification to the sender.

Actions take (envelope, doc, config) and return a dict that goes into the event payload. Other
apps add action types under the frappe_sign_post_sign_actions hook: {"Action name": "dotted.path"}.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

import frappe
from frappe import _
from frappe.utils import add_days, now_datetime, today

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import audit, notify
from frappe_sign.services.template import load_snapshot
from frappe_sign.utils.users import run_as

JOB = "frappe_sign.jobs.actions.run"
EVENT = "Post-Sign Action"
NONE = "None"
# "today", "today+7", "today-1" or "now" in a config value.
RELATIVE_DATE = re.compile(r"^today([+-]\d+)?$")

Action = Callable[[Any, Any, dict[str, Any]], dict[str, Any]]


def action_of(envelope: Any) -> tuple[str, dict[str, Any]]:
	"""The action name and config of the envelope's template version, or ("None", {})."""
	if not envelope.template_version:
		return NONE, {}
	snapshot = load_snapshot(envelope.template_version)
	config = snapshot.get("post_sign_config") or {}
	if isinstance(config, str):
		config = json.loads(config or "{}")
	return snapshot.get("post_sign_action") or NONE, config


def queue_post_sign(envelope: str) -> None:
	"""envelope_completed handler: queue the action job when there is an action to run."""
	doc = frappe.get_doc("Sign Envelope", envelope)
	name, _config = action_of(doc)
	if name == NONE or not doc.reference_doctype or not doc.reference_name:
		return
	frappe.enqueue(JOB, queue="default", enqueue_after_commit=True, envelope=envelope)


def run_post_sign(envelope: str) -> dict[str, Any] | None:
	"""Body of jobs.actions.run. Returns the action's result, or None when there is nothing to do."""
	doc = frappe.get_doc("Sign Envelope", envelope)
	name, config = action_of(doc)
	if name == NONE or doc.status != "Completed":
		return None
	handler = registry().get(name)
	if not handler:
		throw(FieldValidationError, _("Post-sign action {0} is not registered.").format(name))
	with run_as(doc.sender or "Administrator"):
		source = frappe.get_doc(doc.reference_doctype, doc.reference_name)
		result = handler(doc, source, config) or {}
		audit.append(envelope, EVENT, payload={"action": name, "status": "ok", **result})
	return result


def record_failure(envelope: str) -> None:
	"""Called by the job after rolling back a failed action."""
	traceback = frappe.get_traceback()
	frappe.log_error(
		title="Frappe Sign: post-sign action",
		message=f"{envelope}\n\n{traceback}",
		reference_doctype="Sign Envelope",
		reference_name=envelope,
	)
	doc = frappe.get_doc("Sign Envelope", envelope)
	name, _config = action_of(doc)
	error = last_line(traceback)
	audit.append(
		envelope, EVENT, actor="System", payload={"action": name, "status": "failed", "error": error}
	)
	notify.notify_sender(
		doc,
		_("{0}: the post-sign action {1} failed. The signature stands. {2}").format(doc.name, _(name), error),
	)


def last_line(traceback: str) -> str:
	lines = [line for line in traceback.strip().splitlines() if line.strip()]
	return (lines[-1] if lines else "")[:500]


def registry() -> dict[str, Action]:
	actions: dict[str, Action] = dict(BUILTIN)
	for name, paths in frappe.get_hooks("frappe_sign_post_sign_actions", {}).items():
		if paths:
			actions[name] = frappe.get_attr(paths[-1] if isinstance(paths, list) else paths)
	return actions


# Built-in actions


def submit(envelope: Any, doc: Any, config: dict[str, Any]) -> dict[str, Any]:
	if doc.docstatus == 1:
		return {"note": "already submitted"}
	doc.submit()
	return {"submitted": doc.name}


def apply_workflow_action(envelope: Any, doc: Any, config: dict[str, Any]) -> dict[str, Any]:
	from frappe.model.workflow import apply_workflow

	action = config.get("action")
	if not action:
		frappe.throw(_("Set the workflow action in the template's post-sign config."), FieldValidationError)
	updated = apply_workflow(doc, action)
	return {"workflow_action": action, "workflow_state": updated.get("workflow_state")}


def create_mapped_document(envelope: Any, doc: Any, config: dict[str, Any]) -> dict[str, Any]:
	"""Call a whitelisted mapper, such as ERPNext's make_sales_order, and save its result as a draft
	(unless `save` is 0). `values` are set on the new document before it is saved."""
	method = whitelisted(config.get("method"))
	target = method(source_name=doc.name)
	if isinstance(target, dict):
		target = frappe.get_doc(target)
	target.update({key: resolve_value(value) for key, value in (config.get("values") or {}).items()})
	if int(config.get("save", 1)):
		target.insert()
		doc.add_comment(
			"Info",
			_("{0}: created {1} {2} after signing.").format(envelope.name, _(target.doctype), target.name),
		)
	return {"created": target.doctype, "name": target.name}


def set_field_value(envelope: Any, doc: Any, config: dict[str, Any]) -> dict[str, Any]:
	fieldname, value = config.get("fieldname"), config.get("value")
	df = doc.meta.get_field(fieldname) if fieldname else None
	if not df:
		frappe.throw(_("{0} has no field {1}.").format(_(doc.doctype), fieldname or ""), FieldValidationError)
	value = resolve_value(value)
	doc.set(fieldname, value)
	doc.save()
	return {"fieldname": fieldname, "value": str(value)}


def call_method(envelope: Any, doc: Any, config: dict[str, Any]) -> dict[str, Any]:
	method = whitelisted(config.get("method"))
	result = method(envelope=envelope, doc=doc)
	return {
		"method": config.get("method"),
		"result": result if isinstance(result, str | int | float) else None,
	}


def resolve_value(value: Any) -> Any:
	"""Config values may be relative: "now", "today" or "today+N" days."""
	if not isinstance(value, str):
		return value
	if value == "now":
		return now_datetime()
	match = RELATIVE_DATE.match(value)
	return add_days(today(), int(match.group(1) or 0)) if match else value


def whitelisted(path: str | None) -> Callable[..., Any]:
	"""A dotted path that must name a whitelisted function: template authors cannot call anything else."""
	if not path:
		frappe.throw(_("Set the method in the template's post-sign config."), FieldValidationError)
	method = frappe.get_attr(path)
	frappe.is_whitelisted(method)
	return method


BUILTIN: dict[str, Action] = {
	"Submit": submit,
	"Apply Workflow Action": apply_workflow_action,
	"Create Mapped Document": create_mapped_document,
	"Set Field Value": set_field_value,
	"Call Method": call_method,
}
