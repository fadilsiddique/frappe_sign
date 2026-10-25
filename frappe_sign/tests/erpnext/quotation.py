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
