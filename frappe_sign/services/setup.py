"""What setup is still missing, for the Home "Set up signing" panel (UX_PLAN "Home", D18).

Each step reports facts, not sentences: the staff app words them. The steps read site-wide setup
(email accounts, the seal, settings) that a Sign User cannot open, so they use frappe.db reads and
return only summaries, never secrets. Callers need a Frappe Sign role.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe.email.doctype.email_account.email_account import EmailAccount
from frappe.utils import get_datetime, now_datetime

from frappe_sign.services import notify
from frappe_sign.utils.boot import STAFF_ROLES

STEPS = ("email", "seal", "profile", "documents", "template", "test")


def setup_status() -> dict[str, Any]:
	frappe.only_for(list(STAFF_ROLES))
	profile = current_profile()
	steps = [
		email_step(profile),
		seal_step(profile),
		profile_step(profile),
		documents_step(),
		template_step(),
		test_step(),
	]
	return {"steps": steps, "complete": all(step["done"] for step in steps if step["required"])}


def current_profile() -> str | None:
	"""The Sign Profile of the user's default Company, else the oldest one."""
	company = frappe.defaults.get_user_default("company")
	if company and frappe.db.exists("Sign Profile", company):
		return company
	return frappe.db.get_value("Sign Profile", {}, "name", order_by="creation asc")


def step(key: str, done: bool, can_fix: bool, required: bool = True, **facts: Any) -> dict[str, Any]:
	return {"key": key, "done": bool(done), "can_fix": bool(can_fix), "required": required, "facts": facts}


def email_step(profile: str | None) -> dict[str, Any]:
	email_id = outgoing_email(profile)
	return step("email", bool(email_id), frappe.has_permission("Email Account", "write"), email_id=email_id)


def outgoing_email(profile: str | None) -> str | None:
	"""The address invitations go out from: the profile's account, else the default outgoing one.
	Not EmailAccount.find_outgoing: with emails muted it makes up a dummy account."""
	address = notify.sender_address(profile)
	if address and frappe.db.exists("Email Account", {"email_id": address, "enable_outgoing": 1}):
		return address
	account = (
		EmailAccount.find_one_by_filters(enable_outgoing=1, default_outgoing=1)
		or EmailAccount.find_from_config()
	)
	return account.email_id if account else None


def seal_step(profile: str | None) -> dict[str, Any]:
	can_fix = frappe.has_permission("Sign Certificate", "create")
	certificate = profile and frappe.db.get_value("Sign Profile", profile, "sealing_certificate")
	details = certificate and frappe.db.get_value(
		"Sign Certificate", certificate, ["kind", "valid_to"], as_dict=True
	)
	if not details:
		return step("seal", False, can_fix, kind=None, valid_to=None, expired=False)
	expired = bool(details.valid_to) and get_datetime(details.valid_to) <= now_datetime()
	return step(
		"seal",
		not expired,
		can_fix,
		kind=details.kind,
		valid_to=str(details.valid_to.date()) if details.valid_to else None,
		expired=expired,
	)


def profile_step(profile: str | None) -> dict[str, Any]:
	branded = profile and frappe.db.get_value("Sign Profile", profile, ["logo", "brand_color"], as_dict=True)
	return step(
		"profile",
		bool(branded and (branded.logo or branded.brand_color)),
		frappe.has_permission("Sign Profile", "write"),
		profile=profile,
	)


def documents_step() -> dict[str, Any]:
	# Without ERPNext, uploads and templates work without any enabled DocType.
	doctypes = frappe.get_all(
		"Sign Enabled DocType",
		filters={"parenttype": "Sign Settings", "parent": "Sign Settings"},
		pluck="reference_doctype",
		order_by="idx asc",
	)
	return step(
		"documents",
		doctypes,
		frappe.has_permission("Sign Settings", "write"),
		required="erpnext" in frappe.get_installed_apps(),
		doctypes=doctypes,
	)


def template_step() -> dict[str, Any]:
	count = frappe.db.count("Sign Template", {"published_version": ["is", "set"]})
	return step("template", count, frappe.has_permission("Sign Template", "create"), count=count)


def test_step() -> dict[str, Any]:
	sent = frappe.db.exists("Sign Envelope", {"sent_on": ["is", "set"]})
	return step("test", sent, frappe.has_permission("Sign Envelope", "create"))
