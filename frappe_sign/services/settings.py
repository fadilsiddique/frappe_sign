"""Sign Settings values, read from the database so a rolled back change is never served from cache."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint

from frappe_sign.crypto.tsa import tsa_urls_or_default

MB = 1024 * 1024
SETTINGS = "Sign Settings"


def value(fieldname: str) -> object:
	return frappe.db.get_single_value(SETTINGS, fieldname)


def max_upload_bytes() -> int:
	return (cint(value("max_upload_mb")) or 20) * MB


def max_pages() -> int:
	return cint(value("max_pages")) or 200


def expiry_days() -> int:
	return cint(value("default_expiry_days")) or 14


def reminder_days() -> int:
	return cint(value("default_reminder_days"))


def otp_validity_minutes() -> int:
	return cint(value("otp_validity_minutes")) or 10


def tsa_urls() -> list[str]:
	return tsa_urls_or_default(str(value("tsa_urls") or "").splitlines())


def consent() -> tuple[str, int]:
	"""The disclosure shown to signers and its version. A built-in text stands in until one is set."""
	text = str(value("consent_text") or "").strip()
	if not text:
		return default_consent_text(), 0
	return text, cint(value("consent_version"))


def default_consent_text() -> str:
	return _(
		"By continuing, you agree to sign this document electronically. Your electronic signature is "
		"legally binding in the same way as a handwritten signature. You can ask the sender for a paper "
		"copy. Your IP address, device and the time of each step are recorded."
	)
