"""Sign Envelope visibility (DESIGN 1): Sign Managers see everything; a Sign User sees envelopes they
sent, envelopes they are a recipient of (by email) and envelopes shared with them. Only the sender,
a Sign Manager or a user it is shared with for writing may change an envelope.

Frappe runs controller permission hooks before role permissions and sharing, so the hook allows
shared envelopes itself.
"""

import frappe

MANAGER_ROLES = frozenset({"Sign Manager", "System Manager"})
READ_ONLY = ("read", "print", "email", "report", "export")


def is_manager(user: str) -> bool:
	return user == "Administrator" or bool(MANAGER_ROLES & set(frappe.get_roles(user)))


def user_email(user: str) -> str:
	return frappe.db.get_value("User", user, "email") or user


def is_recipient(envelope: str, user: str) -> bool:
	return bool(
		frappe.db.exists(
			"Sign Envelope Recipient",
			{"parent": envelope, "parenttype": "Sign Envelope", "email": user_email(user)},
		)
	)


def is_shared(envelope: str, user: str, ptype: str) -> bool:
	right = "read" if ptype in READ_ONLY else ptype
	if right not in ("read", "write", "share", "submit"):
		return False
	return bool(
		frappe.share.get_shared(
			"Sign Envelope", user, rights=[right], filters=[["share_name", "=", envelope]], limit=1
		)
	)


def envelope_has_permission(doc, ptype=None, user=None, debug=False) -> bool:
	user = user or frappe.session.user
	ptype = ptype or "read"
	if is_manager(user):
		return True
	if doc.get("sender") == user or doc.get("owner") == user or doc.is_new():
		return True
	if is_shared(doc.name, user, ptype):
		return True
	return ptype in READ_ONLY and is_recipient(doc.name, user)


def envelope_query_conditions(user=None) -> str:
	user = user or frappe.session.user
	if is_manager(user):
		return ""
	quoted_user, quoted_email = frappe.db.escape(user), frappe.db.escape(user_email(user))
	return (
		f"(`tabSign Envelope`.`sender` = {quoted_user} or `tabSign Envelope`.`owner` = {quoted_user}"
		" or `tabSign Envelope`.`name` in (select `parent` from `tabSign Envelope Recipient`"
		f" where `parenttype` = 'Sign Envelope' and `email` = {quoted_email}))"
	)
