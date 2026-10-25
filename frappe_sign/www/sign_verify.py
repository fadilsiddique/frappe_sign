"""Public verify page at /sign-verify (DESIGN 5.6). The certificate's QR code links here with
?envelope=<id>. The page calls frappe_sign.api.public.verify, which is rate limited."""

import frappe
from frappe import _

no_cache = 1
sitemap = 0


def get_context(context):
	context.no_breadcrumbs = True
	context.title = _("Verify a signed document")
	request = getattr(frappe.local, "request", None)
	query = request.args.get("envelope") if request else None
	envelope = str(frappe.form_dict.get("envelope") or query or "").strip()
	context.envelope = envelope if len(envelope) <= 140 else ""
