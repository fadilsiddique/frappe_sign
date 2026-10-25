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


def make_private_file(file_name: str, content: bytes, **overrides):
	return frappe.get_doc(
		{"doctype": "File", "file_name": file_name, "content": content, "is_private": 1, **overrides}
	).insert(ignore_if_duplicate=True)


def make_certificate(p12_name: str = "sealing.p12", password: str = "fixture-seal", **overrides):
	"""A Sign Certificate holding one of the test PKI's PKCS#12 files (tests/fixtures/certs/)."""
	from frappe_sign.tests.pki import CERTS

	p12 = make_private_file(p12_name, (CERTS / p12_name).read_bytes())
	return frappe.get_doc(
		{
			"doctype": "Sign Certificate",
			"title": "Test Seal",
			"storage": "PKCS#12 File",
			"p12_file": p12.file_url,
			"p12_password": password,
			**overrides,
		}
	).insert()


def make_user(email: str, *roles: str):
	"""A Desk user with the given roles, created once per test transaction."""
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{"doctype": "User", "email": email, "first_name": email.split("@")[0], "send_welcome_email": 0}
		).insert()
	user.add_roles(*roles)
	return user


def fixture_pdf(name: str = "a4_simple.pdf") -> bytes:
	from pathlib import Path

	return (Path(__file__).resolve().parent / "fixtures" / "pdfs" / name).read_bytes()
