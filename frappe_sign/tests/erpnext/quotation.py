"""A published Quotation template: Print Format with sign_field() anchors, Customer and Company."""

import frappe

from frappe_sign.services import template as template_service
from frappe_sign.tests.erpnext.test_anchors_quotation import QUOTATION_HTML
from frappe_sign.tests.printing import make_print_format


def publish_quotation_template(generator: str = "chrome", customer_only: bool = False, **extra) -> str:
	"""The template's name. Customer comes from the Quotation, Company is the Administrator.
	With `customer_only`, the Company role is a CC, so the Customer's signature completes it."""
	print_format = make_print_format("Quotation", QUOTATION_HTML, generator)
	template = template_service.create_template(
		{
			"title": "Quotation acceptance",
			"source_type": "Print Format",
			"reference_doctype": "Quotation",
			"print_format": print_format.name,
			"signing_order": "Sequential",
			"roles": [
				{
					"role_label": "Customer",
					"kind": "Signer",
					"signer_source": "Party Contact",
					"routing_order": 1,
				},
				{
					"role_label": "Company",
					"kind": "CC" if customer_only else "Signer",
					"signer_source": "Fixed User",
					"fixed_user": "Administrator",
					"routing_order": 2,
				},
			],
			"fields": [],
			**extra,
		}
	)
	template_service.publish(template.name)
	return template.name


def default_template_for(doctype: str, template: str) -> None:
	settings = frappe.get_single("Sign Settings")
	for row in settings.enabled_doctypes:
		if row.reference_doctype == doctype:
			row.default_template = template
	settings.save()


def signed_quotation(quotation: str, template: str) -> str:
	"""Send the Quotation with the template, let the Customer sign and seal it offline. Returns the
	envelope, now Completed. Jobs do not run: the caller runs the event handlers it tests."""
	from unittest.mock import patch

	from frappe_sign.jobs import seal as seal_job
	from frappe_sign.services import documents, signing
	from frappe_sign.services import envelope as envelope_service
	from frappe_sign.services.resolvers import resolve_recipients
	from frappe_sign.tests.erpnext.test_send_from_document import fake_chrome
	from frappe_sign.tests.factories import make_profile
	from frappe_sign.tests.integration.test_sealing import no_commits, offline_seal
	from frappe_sign.tests.integration.test_signing_service import CLIENT
	from frappe_sign.tests.signing_helpers import capture_tokens
	from frappe_sign.tests.unit.test_overlay import signature_png

	make_profile()
	rows = resolve_recipients(template, "Quotation", quotation)
	with patch("frappe.enqueue"):
		name = documents.send_from_document("Quotation", quotation, template, rows)
	with (
		capture_tokens() as box,
		patch("frappe.utils.pdf.get_chrome_pdf", side_effect=fake_chrome),
		patch("frappe.enqueue"),
	):
		envelope_service.render_and_send(name)
	customer = next(
		row for row in frappe.get_doc("Sign Envelope", name).recipients if row.role_label == "Customer"
	)
	opened = signing.open(box[customer.name], CLIENT)
	signing.consent(opened["session"], opened["consent"]["version"], CLIENT)
	signing.save_capture(opened["session"], "customer_signature_1", "Draw", signature_png(), client=CLIENT)
	with patch("frappe.enqueue"):
		signing.finish(opened["session"], CLIENT)
	with offline_seal(), no_commits(), patch("frappe.enqueue"):
		seal_job.run(name)
	return name
