"""Domain events: publish enqueues one jobs.events.run job per handler after commit (D17).

Handlers are dotted paths registered under the frappe_sign_events hook. Each runs in its own job,
which commits, so a handler's writes persist and a failing handler never rolls back the change that
published the event.
"""

from __future__ import annotations

import frappe

from frappe_sign.utils.users import run_as

EVENTS = (
	"envelope_sent",
	"recipient_viewed",
	"recipient_signed",
	"envelope_declined",
	"envelope_voided",
	"envelope_completed",
)
JOB = "frappe_sign.jobs.events.run"


def handlers(event: str) -> list[str]:
	return list(frappe.get_hooks("frappe_sign_events", {}).get(event, []))


def publish(event: str, envelope: str) -> None:
	if event not in EVENTS:
		raise ValueError(f"Unknown Frappe Sign event {event}")
	for handler in handlers(event):
		frappe.enqueue(
			JOB,
			queue="default",
			enqueue_after_commit=True,
			handler=handler,
			event=event,
			envelope=envelope,
		)


def run_handler(handler: str, event: str, envelope: str) -> None:
	"""Run as the envelope sender: events that a guest causes would otherwise run as Guest, and
	handlers write data that needs the sender's permissions (DESIGN 4.6, 8.5)."""
	if handler not in handlers(event):
		raise ValueError(f"{handler} is not registered for {event}")
	sender = frappe.db.get_value("Sign Envelope", envelope, "sender") or "Administrator"
	with run_as(sender):
		frappe.get_attr(handler)(envelope)


def record_failure(handler: str, event: str, envelope: str) -> None:
	"""Called by the job after rolling back a failed handler. The traceback goes to the Error Log."""
	frappe.log_error(
		title=f"Frappe Sign: event handler {event}",
		message=f"{handler} failed for {envelope}\n\n{frappe.get_traceback()}",
		reference_doctype="Sign Envelope",
		reference_name=envelope,
	)
