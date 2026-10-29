"""Portal API: download one's own signed document (DESIGN 4.9). Login required, never guest."""

import frappe
from werkzeug.wrappers import Response

from frappe_sign.services import portal


@frappe.whitelist(methods=["GET"])
def download(envelope: str) -> Response:
	data, file_name = portal.download(envelope)
	return Response(
		data,
		mimetype="application/pdf",
		headers={
			"Content-Disposition": f'attachment; filename="{file_name}"',
			"Cache-Control": "no-store",
			"X-Content-Type-Options": "nosniff",
		},
	)
