"""Response headers for the guest signing pages and API (DESIGN 5.2)."""

GUEST_PREFIXES = ("/s/", "/api/method/frappe_sign.api.guest.")


def after_request(response=None, request=None) -> None:
	"""The link token is in the /s/ path: never send it on as a Referer, and never cache the page."""
	path = getattr(request, "path", "") or ""
	if response is None or not path.startswith(GUEST_PREFIXES):
		return
	response.headers["Referrer-Policy"] = "no-referrer"
	response.headers["Cache-Control"] = "no-store"
	response.headers["X-Robots-Tag"] = "noindex, nofollow"
