"""Build published templates and sent envelopes for service tests, and capture emailed tokens."""

from contextlib import contextmanager
from unittest.mock import patch

import frappe

from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import notify
from frappe_sign.services import template as template_service
from frappe_sign.tests.factories import fixture_pdf, signature_field

CUSTOMER = {"role_label": "Customer", "full_name": "Ahmed Khan", "email": "ahmed@example.com"}
COMPANY = {"role_label": "Company", "full_name": "Fatima Ali", "email": "fatima@example.com"}


def two_signer_roles(signing_order: str = "Sequential") -> list[dict]:
	return [
		{
			"role_label": "Customer",
			"kind": "Signer",
			"signer_source": "Ask at Send",
			"routing_order": 1,
			"can_delegate": 1,
		},
		{
			"role_label": "Company",
			"kind": "Signer",
			"signer_source": "Ask at Send",
			"routing_order": 1 if signing_order == "Parallel" else 2,
		},
	]


def two_signer_fields() -> list[dict]:
	return [
		signature_field(),
		signature_field(field_key="customer_name", field_type="Full Name", y=0.7, h=0.03),
		signature_field(field_key="customer_date", field_type="Date Signed", y=0.75, h=0.03),
		signature_field(field_key="company_signature", role_label="Company", y=0.9),
	]


def publish_template(
	signing_order: str = "Sequential",
	otp_mode: str = "Off",
	roles: list[dict] | None = None,
	fields: list[dict] | None = None,
	pdf: str = "a4_simple.pdf",
	**extra,
) -> str:
	template = template_service.create_template(
		{
			"title": "Service Agreement",
			"source_type": "Uploaded PDF",
			"signing_order": signing_order,
			"otp_mode": otp_mode,
			"roles": roles if roles is not None else two_signer_roles(signing_order),
			"fields": fields if fields is not None else two_signer_fields(),
			**extra,
		}
	)
	template_service.upload_pdf(template.name, "agreement.pdf", fixture_pdf(pdf))
	return template_service.publish(template.name).name


def make_draft(version: str | None = None, recipients: list[dict] | None = None, **payload):
	return envelope_service.create_draft(
		{
			"template_version": version or publish_template(),
			"recipients": recipients or [CUSTOMER, COMPANY],
			**payload,
		}
	)


class TokenBox:
	"""Plain tokens emailed in invitations, by recipient row name (latest wins)."""

	def __init__(self):
		self.tokens: dict[str, str] = {}
		self.sent: list[tuple[str, str, bool]] = []

	def __getitem__(self, row: str) -> str:
		return self.tokens[row]


@contextmanager
def capture_tokens():
	box = TokenBox()
	original = notify.send_invitation

	def record(envelope, recipient, token, *, reminder=False):
		box.tokens[recipient.name] = token
		box.sent.append((recipient.name, recipient.email, reminder))
		original(envelope, recipient, token, reminder=reminder)

	with patch.object(notify, "send_invitation", side_effect=record):
		yield box


def send_now(name: str) -> None:
	"""send() and then the render job body, without a worker."""
	with patch("frappe.enqueue"):
		envelope_service.send(name)
	envelope_service.render_and_send(name)


def recipients_by_role(name: str) -> dict:
	doc = frappe.get_doc("Sign Envelope", name)
	return {row.role_label: row for row in doc.recipients}
