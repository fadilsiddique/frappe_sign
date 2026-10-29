"""The languages Frappe Sign ships: English and Arabic (P3.5)."""

from __future__ import annotations

import frappe

SHIPPED = ("en", "ar")


def base_language(language: str | None) -> str:
	return str(language or "").split("-")[0].lower()


def is_arabic(language: str | None) -> bool:
	return base_language(language) == "ar"


def shipped_language(language: str | None) -> str:
	"""`ar` for any Arabic variant, otherwise `en`: the languages the app has texts for."""
	return "ar" if is_arabic(language) else "en"


def user_language(user: str | None = None) -> str:
	"""A user's own language, else the site's, as `en` or `ar`."""
	from frappe.translate import get_user_lang

	return shipped_language(get_user_lang(user or frappe.session.user))
