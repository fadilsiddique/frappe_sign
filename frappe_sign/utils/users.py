"""Run code as another user and restore the session user afterwards."""

from collections.abc import Iterator
from contextlib import contextmanager

import frappe


@contextmanager
def run_as(user: str) -> Iterator[None]:
	"""Used in jobs only: sealing and post-sign actions run as the envelope sender (DESIGN 4.6),
	so the sender's permissions apply, never more."""
	previous = frappe.session.user
	frappe.set_user(user)  # nosemgrep: frappe-setuser
	try:
		yield
	finally:
		frappe.set_user(previous)  # nosemgrep: frappe-setuser
