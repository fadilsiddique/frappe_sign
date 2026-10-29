"""Shims for Frappe and ERPNext APIs newer than v16.0.0 (D15).

The app may only call framework APIs that exist in the v16.0.0 tags. When a newer API is worth
using, wrap it here with feature detection (`hasattr` or a guarded import) and a fallback that
works on v16.0.0. Never compare version strings.

Soft dependencies (frappe_whatsapp, ERPNext) are detected with `app_installed`.
"""


def app_installed(app: str) -> bool:
	"""True when `app` is installed on the current site (soft dependencies such as frappe_whatsapp)."""
	import frappe

	return app in frappe.get_installed_apps()
