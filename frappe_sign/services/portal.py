"""Portal "My Documents" (DESIGN 4.9): a logged-in person sees and downloads the documents they signed.

Identity is the logged-in user's email, matched to a Signer or Approver row that signed. Nothing
else about the envelope is returned: no source document, no other recipients. Reads here bypass
document permissions on purpose (portal users have none on Sign Envelope), so every query is
filtered by that email, and a name that is not theirs gets the same error as one that does not exist.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from frappe_sign.exceptions import FieldValidationError, throw
from frappe_sign.services import audit
from frappe_sign.utils.files import read_file

SIGNING_KINDS = ("Signer", "Approver")
MAX_NAME_LENGTH = 140
LIST_LIMIT = 200


def user_email(user: str) -> str:
	if not user or user == "Guest":
		return ""
	return str(frappe.db.get_value("User", user, "email") or "").strip().lower()


def signed_documents(user: str) -> list[dict[str, Any]]:
	"""Completed envelopes the user signed, newest first."""
	names = signed_envelope_names(user_email(user))
	if not names:
		return []
	return frappe.get_all(
		"Sign Envelope",
		filters={"name": ["in", names], "status": "Completed", "signed_file": ["is", "set"]},
		fields=["name", "title", "company", "completed_on"],
		order_by="completed_on desc",
		limit=LIST_LIMIT,
	)


def signed_envelope_names(email: str) -> list[str]:
	"""Envelopes with a signed Signer or Approver row for `email`. MariaDB compares emails without
	regard to case, so no LOWER() is needed (and the index stays usable)."""
	if not email:
		return []
	return frappe.get_all(
		"Sign Envelope Recipient",
		filters={
			"parenttype": "Sign Envelope",
			"kind": ["in", SIGNING_KINDS],
			"status": "Signed",
			"email": email,
		},
		pluck="parent",
	)


def download(name: str) -> tuple[bytes, str]:
	"""The sealed PDF of one of the user's own documents; records a Downloaded event."""
	if len(str(name or "")) > MAX_NAME_LENGTH:
		throw(FieldValidationError, _("This is not a valid document name."))
	user = frappe.session.user
	allowed = {row["name"]: row for row in signed_documents(user)}
	if name not in allowed:
		raise frappe.PermissionError(_("You cannot download this document."))
	signed_file = frappe.db.get_value("Sign Envelope", name, "signed_file")
	data = read_file(signed_file)
	audit.append(name, "Downloaded", actor=user_email(user), payload={"kind": "signed", "channel": "portal"})
	return data, f"{name}-signed.pdf"
