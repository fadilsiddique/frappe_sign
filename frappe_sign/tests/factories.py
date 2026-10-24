"""Builders for test documents. Callers own cleanup (IntegrationTestCase rolls back)."""

import frappe
from frappe.utils import now_datetime

from frappe_sign.utils.hashing import sha256_hex

PRIVATE_PDF = "/private/files/frappe-sign-test.pdf"
PRIVATE_PNG = "/private/files/frappe-sign-test.png"


def signature_field(**overrides) -> dict:
	return {
		"field_key": "customer_signature",
		"role_label": "Customer",
		"field_type": "Signature",
		"page": 1,
		"x": 0.1,
		"y": 0.8,
		"w": 0.3,
		"h": 0.08,
		**overrides,
	}


def make_template(**overrides):
	return frappe.get_doc(
		{
			"doctype": "Sign Template",
			"title": "Test Template",
			"source_type": "Uploaded PDF",
			"pdf_file": PRIVATE_PDF,
			"roles": [{"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send"}],
			"fields": [signature_field()],
			**overrides,
		}
	).insert()


def make_template_version(template=None, version_no=1):
	template = template or make_template()
	return frappe.get_doc(
		{
			"doctype": "Sign Template Version",
			"template": template.name,
			"version_no": version_no,
			"snapshot": frappe.as_json({"title": template.title}),
			"source_sha256": sha256_hex(b"pdf"),
			"published_by": frappe.session.user,
			"published_on": now_datetime(),
		}
	).insert()


def make_envelope(**overrides):
	return frappe.get_doc(
		{
			"doctype": "Sign Envelope",
			"title": "Test Envelope",
			"recipients": [
				{
					"role_label": "Customer",
					"kind": "Signer",
					"full_name": "Test Signer",
					"email": "signer@example.com",
				}
			],
			"fields": [signature_field()],
			**overrides,
		}
	).insert()


def make_event(envelope, seq=1, **overrides):
	return frappe.get_doc(
		{
			"doctype": "Sign Event",
			"envelope": envelope.name,
			"seq": seq,
			"event": "Created",
			"at": now_datetime(),
			"actor": frappe.session.user,
			"prev_hash": sha256_hex(envelope.name),
			"hash": sha256_hex(f"{envelope.name}:{seq}"),
			**overrides,
		}
	).insert()


def make_capture(envelope, **overrides):
	return frappe.get_doc(
		{
			"doctype": "Sign Capture",
			"envelope": envelope.name,
			"recipient_row": envelope.recipients[0].name,
			"field_key": "customer_signature",
			"method": "Draw",
			"image": PRIVATE_PNG,
			"sha256": sha256_hex(b"png"),
			**overrides,
		}
	).insert()
