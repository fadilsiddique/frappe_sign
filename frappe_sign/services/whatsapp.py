"""WhatsApp delivery through frappe_whatsapp, a soft dependency (DESIGN 8.7).

Nothing here imports frappe_whatsapp: a WhatsApp Message document is inserted and its own
controller sends it. Without the app, `available` is False and every caller falls back to email.
Free-form text reaches a number only inside Meta's 24 hour window, so sites that message cold
numbers need an approved template in frappe_whatsapp (see the admin guide).
"""

from __future__ import annotations

from typing import Any

import frappe

from frappe_sign.compat import app_installed

APP = "frappe_whatsapp"
MESSAGE = "WhatsApp Message"


def available() -> bool:
	return app_installed(APP) and bool(frappe.db.exists("DocType", MESSAGE))


def enabled(company: str | None) -> bool:
	"""frappe_whatsapp is installed and the company's Sign Profile switched WhatsApp on."""
	if not available() or not company:
		return False
	return bool(frappe.db.get_value("Sign Profile", company, "whatsapp_enabled"))


def any_enabled() -> bool:
	return available() and bool(frappe.db.exists("Sign Profile", {"whatsapp_enabled": 1}))


def message(to: str, text: str, envelope: str) -> Any:
	"""An unsaved outgoing WhatsApp Message. Inserting it makes frappe_whatsapp send it."""
	return frappe.get_doc(
		{
			"doctype": MESSAGE,
			"type": "Outgoing",
			"to": to,
			"message": text,
			"content_type": "text",
			"reference_doctype": "Sign Envelope",
			"reference_name": envelope,
		}
	)


def send_text(to: str, text: str, envelope: str) -> None:
	"""Send as the current user, whose permissions apply. Raises when frappe_whatsapp cannot send."""
	message(to, text, envelope).insert()


def mask_mobile(mobile: str | None) -> str:
	digits = "".join(ch for ch in str(mobile or "") if ch.isdigit())
	return f"{'*' * max(len(digits) - 3, 0)}{digits[-3:]}" if len(digits) > 3 else ""


def invitation_text(envelope: Any, recipient: Any, link: str, *, reminder: bool = False) -> str:
	lead = "Reminder: please sign" if reminder else "Please sign"
	return f"{frappe._(lead)} {envelope.title}\n{link}"


def otp_text(envelope: Any, code: str, minutes: int) -> str:
	return frappe._("Your code for {0}: {1}. It is valid for {2} minutes.").format(
		envelope.title, code, minutes
	)
