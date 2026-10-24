"""Guest signing shell at /s/<token>. www/s.html is copied here by the frontend build.

Guests get no CSRF token: guest API calls authenticate with the X-Sign-Session header (D10).
Branding for the envelope's Company is loaded with the envelope (P1.14).
"""

from frappe_sign.utils.boot import base_boot

no_cache = 1
sitemap = 0


def get_context(context):
	context.boot = {"frappe_sign": base_boot(user=None)}
