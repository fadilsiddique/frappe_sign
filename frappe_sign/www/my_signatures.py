"""Portal page /my-signatures: the documents the logged-in person has signed (DESIGN 4.9)."""

from urllib.parse import quote

import frappe
from frappe import _

from frappe_sign.services import portal

no_cache = 1
sitemap = 0


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = f"/login?redirect-to={quote('/my-signatures')}"
		raise frappe.Redirect(302)
	context.no_breadcrumbs = True
	context.title = _("My signed documents")
	context.documents = portal.signed_documents(frappe.session.user)
