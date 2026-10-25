"""The caller's IP address and user agent, for Sign Events and Sign Sessions."""

from dataclasses import dataclass

import frappe

USER_AGENT_LIMIT = 1000


@dataclass(frozen=True)
class Client:
	ip: str | None = None
	user_agent: str | None = None


def current_client() -> Client:
	"""The client of the current request, or an empty Client in jobs and the console."""
	if not getattr(frappe.local, "request", None):
		return Client()
	user_agent = frappe.get_request_header("User-Agent") or None
	return Client(
		ip=getattr(frappe.local, "request_ip", None) or None,
		user_agent=user_agent[:USER_AGENT_LIMIT] if user_agent else None,
	)
