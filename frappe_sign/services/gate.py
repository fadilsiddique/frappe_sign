"""The cached set of DocTypes the `*` dispatcher looks at (D8, DESIGN 4.7).

A DocType is in the gate when it has an enabled Sign Trigger, is enabled in Sign Settings, or has
an open envelope. Every other document event costs the dispatcher one cache lookup and no query.
The set is rebuilt from the database on a miss and cleared when a trigger or Sign Settings is
saved, or an envelope opens for a DocType outside it. A DocType that stays in the set after its
last envelope closes only costs the dispatcher a query that finds nothing.
"""

from __future__ import annotations

import frappe

KEY = "frappe_sign::gated_doctypes"
OPEN = ("Sent", "In Progress")


def gated_doctypes() -> frozenset[str]:
	return frappe.cache.get_value(KEY, generator=build)


def build() -> frozenset[str]:
	triggers = frappe.get_all(
		"Sign Trigger", filters={"enabled": 1}, pluck="reference_doctype", distinct=True
	)
	enabled = frappe.get_all(
		"Sign Enabled DocType", filters={"parenttype": "Sign Settings"}, pluck="reference_doctype"
	)
	opened = frappe.get_all(
		"Sign Envelope",
		filters={"status": ["in", OPEN], "reference_doctype": ["is", "set"]},
		pluck="reference_doctype",
		distinct=True,
	)
	return frozenset(name for name in (*triggers, *enabled, *opened) if name)


def clear(*args: object, **kwargs: object) -> None:
	"""Drop the set now and again after commit, so a rebuild in between cannot keep it stale.
	Takes any arguments, so it can be a doc_events handler."""
	frappe.cache.delete_value(KEY)
	frappe.db.after_commit.add(lambda: frappe.cache.delete_value(KEY))


def include(doctype: str | None) -> None:
	"""An envelope opened for `doctype`: make sure the dispatcher sees its events."""
	if doctype and doctype not in gated_doctypes():
		clear()
