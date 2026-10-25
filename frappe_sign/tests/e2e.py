"""Fixtures for the Playwright tests in e2e/. Run through `bench execute`, which commits.

    bench --site sign.localhost execute frappe_sign.tests.e2e.create_guest_envelope
    bench --site sign.localhost execute frappe_sign.tests.e2e.purge --kwargs '{"envelope": "...", "started": "..."}'

Both refuse to run unless the site has allow_tests set, so they never touch a working site.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

from frappe_sign.tests.cleanup import purge_envelope, purge_profile, purge_since, purge_template
from frappe_sign.tests.factories import make_email_account
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now
from frappe_sign.utils.users import run_as


def require_test_site() -> None:
	if not frappe.conf.allow_tests:
		frappe.throw(frappe._("Frappe Sign e2e fixtures run only on sites with allow_tests set."))


def create_guest_envelope(otp_mode: str = "Off") -> dict:
	"""A sent envelope (Customer then Company) and the Customer's signing token."""
	require_test_site()
	started = now_datetime()
	with run_as("Administrator"):
		make_email_account(skip_smtp_check=True)
		draft = make_draft(publish_template(otp_mode=otp_mode), title="E2E Service Agreement")
		with capture_tokens() as box:
			send_now(draft.name)
	customer = next(
		row for row in frappe.get_doc("Sign Envelope", draft.name).recipients if row.role_label == "Customer"
	)
	return {"envelope": draft.name, "token": box[customer.name], "started": str(started)}


def envelope_state(envelope: str) -> dict:
	require_test_site()
	doc = frappe.get_doc("Sign Envelope", envelope)
	return {
		"status": doc.status,
		"recipients": {row.role_label: row.status for row in doc.recipients},
		"fields": {row.field_key: bool(row.value or row.capture) for row in doc.fields},
	}


def purge(envelope: str, started: str) -> None:
	require_test_site()
	for template in purge_envelope(envelope):
		purge_template(template)
	purge_since(get_datetime(started))


def purge_created(started: str) -> dict:
	"""Delete envelopes and templates created since `started` (a staff e2e run), with their files."""
	require_test_site()
	since = get_datetime(started)
	envelopes = frappe.get_all("Sign Envelope", filters={"creation": [">=", since]}, pluck="name")
	templates = set(frappe.get_all("Sign Template", filters={"creation": [">=", since]}, pluck="name"))
	for envelope in envelopes:
		templates.update(purge_envelope(envelope))
	for template in templates:
		purge_template(template)
	purge_since(since)
	return {"envelopes": len(envelopes), "templates": len(templates)}


def prepare_staff() -> dict:
	"""An outgoing Email Account for sending, and the start time for purge_created."""
	require_test_site()
	started = now_datetime()
	make_email_account(skip_smtp_check=True)
	return {"now": str(started)}


# ERPNext: a Quotation sent from its Desk form (P2.5) and signed end to end (Gate 2).

ERPNEXT_PURGE = (
	("Quotation", ("Quotation Item", "Sales Taxes and Charges", "Payment Schedule")),
	("Sales Order", ("Sales Order Item", "Sales Taxes and Charges", "Payment Schedule")),
	("Customer", ()),
	("Contact", ("Contact Email", "Contact Phone", "Dynamic Link")),
	("Item", ("Item Default", "UOM Conversion Detail", "Item Barcode")),
	("Item Price", ()),
	("Print Format", ()),
	("Sign Template", ("Sign Template Role", "Sign Template Field")),
	("Sign Template Version", ()),
	("Comment", ()),
	("Communication", ()),
	("Notification Log", ()),
	("Error Log", ()),
	("Sign Trigger Log", ()),
	("Access Log", ()),
)


def prepare_quotation(submit: bool = True, items: int = 3, post_sign_action: str = "None") -> dict:
	"""A Quotation for Gulf Trading LLC, Quotation enabled for signing and a published template."""
	require_test_site()
	from frappe_sign.tests.doctypes import enable_doctypes
	from frappe_sign.tests.erpnext.helpers import make_quotation
	from frappe_sign.tests.erpnext.quotation import publish_quotation_template
	from frappe_sign.tests.factories import make_profile

	started = now_datetime()
	enable_doctypes("Quotation")
	with run_as("Administrator"):
		make_email_account(skip_smtp_check=True)
		make_profile()
		quotation = make_quotation(items=items, submit=submit)
		template = publish_quotation_template(
			customer_only=True,
			post_sign_action=post_sign_action,
			post_sign_config=SALES_ORDER_ACTION if post_sign_action == "Create Mapped Document" else None,
		)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (e2e fixtures commit for the browser)
	return {"quotation": quotation.name, "template": template, "started": str(started)}


SALES_ORDER_ACTION = frappe.as_json(
	{
		"method": "erpnext.selling.doctype.quotation.quotation.make_sales_order",
		"save": 1,
		"values": {"delivery_date": "today+7"},
	}
)


def document_state(doctype: str, name: str) -> dict:
	"""The newest envelope of a document and the document's signature fields."""
	require_test_site()
	envelope = frappe.db.get_value(
		"Sign Envelope",
		{"reference_doctype": doctype, "reference_name": name},
		["name", "status", "send_state", "send_error", "sealing_state"],
		as_dict=True,
		order_by="creation desc",
	)
	values = frappe.db.get_value(doctype, name, ["sign_status", "sign_envelope", "docstatus"], as_dict=True)
	attachments = frappe.get_all(
		"File", filters={"attached_to_doctype": doctype, "attached_to_name": name}, pluck="file_name"
	)
	orders = (
		frappe.get_all("Sales Order Item", filters={"prevdoc_docname": name}, pluck="parent", distinct=True)
		if doctype == "Quotation"
		else []
	)
	return {
		"envelope": envelope,
		"document": values,
		"attachments": attachments,
		"sales_orders": [
			frappe.db.get_value("Sales Order", order, ["name", "docstatus"], as_dict=True) for order in orders
		],
	}


def render_if_queued(envelope: str) -> dict:
	"""Run the render job inline when no worker has picked it up."""
	require_test_site()
	from frappe_sign.jobs import render

	if frappe.db.get_value("Sign Envelope", envelope, "send_state") == "Queued":
		with run_as(frappe.db.get_value("Sign Envelope", envelope, "sender")):
			render.run(envelope)
	return frappe.db.get_value(
		"Sign Envelope", envelope, ["status", "send_state", "send_error"], as_dict=True
	)


def signing_token(envelope: str, email: str) -> dict:
	"""{"token": the /s/<token> from the newest invitation email to `email` for this envelope}."""
	return {"token": invitation_token(envelope, email)}


def invitation_token(envelope: str, email: str) -> str | None:
	require_test_site()
	import email as email_parser
	import re

	reference = frappe.db.get_value("Sign Envelope", envelope, ["reference_doctype", "reference_name"])
	for queue in frappe.get_all(
		"Email Queue",
		filters={"reference_name": ["in", [envelope, reference[1]]]},
		fields=["name", "message"],
		order_by="creation desc",
	):
		recipients = frappe.get_all(
			"Email Queue Recipient", filters={"parent": queue.name}, pluck="recipient"
		)
		if email not in recipients:
			continue
		message = email_parser.message_from_string(queue.message)
		for part in message.walk():
			if part.get_content_type() == "text/html":
				body = part.get_payload(decode=True).decode()
				found = re.search(r"/s/([A-Za-z0-9_-]{20,})", body)
				if found:
					return found.group(1)
	return None


def purge_quotation(started: str) -> dict:
	"""Delete what prepare_quotation and the browser created since `started`, and the fields."""
	require_test_site()
	from frappe_sign.tests.doctypes import disable_doctypes

	since = get_datetime(started)
	result = purge_created(started)
	for doctype, children in ERPNEXT_PURGE:
		names = frappe.get_all(doctype, filters={"creation": [">=", since]}, pluck="name")
		for child in children:
			if names:
				frappe.db.delete(child, {"parent": ["in", names]})
		if names:
			frappe.db.delete(doctype, {"name": ["in", names]})
		result[doctype] = len(names)
	for profile in frappe.get_all("Sign Profile", filters={"creation": [">=", since]}, pluck="name"):
		purge_profile(profile)
	frappe.db.delete("Email Queue", {"creation": [">=", since]})
	frappe.db.delete("Version", {"creation": [">=", since]})
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (e2e fixtures commit for the browser)
	disable_doctypes("Quotation")
	return result


def complete_pending(envelope: str) -> dict:
	"""Gate 2: when no worker has sealed the envelope, seal it here with the offline test PKI,
	then run the jobs that sealing queues (event handlers, post-sign action), each committing."""
	require_test_site()
	from unittest.mock import patch

	from frappe_sign.jobs import seal as seal_job
	from frappe_sign.tests.integration.test_sealing import offline_seal

	state = frappe.db.get_value("Sign Envelope", envelope, "sealing_state")
	if state not in ("Queued", "Failed"):
		return {"sealing_state": state, "ran": 0}
	if state == "Failed":
		frappe.db.set_value("Sign Envelope", envelope, {"sealing_state": "Queued", "seal_retry_on": None})
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (e2e fixtures commit for the browser)
	queued: list[tuple[str, dict]] = []

	def record(method, **kwargs):
		queued.append((method, kwargs))

	sender = frappe.db.get_value("Sign Envelope", envelope, "sender")
	with patch("frappe.enqueue", side_effect=record), offline_seal(), run_as(sender):
		seal_job.run(envelope)
		ran = 0
		while queued:
			method, kwargs = queued.pop(0)
			params = {k: v for k, v in kwargs.items() if k not in JOB_OPTIONS}
			frappe.get_attr(method)(**params)
			ran += 1
	return {"sealing_state": frappe.db.get_value("Sign Envelope", envelope, "sealing_state"), "ran": ran}


JOB_OPTIONS = {"queue", "timeout", "job_id", "deduplicate", "enqueue_after_commit", "now", "at_front"}


# Sign Certificate: "Create test certificate" from Desk.


def prepare_certificate() -> dict:
	"""The company the dialog defaults to, and the start time for purge_certificates."""
	require_test_site()
	from frappe_sign.tests.factories import test_company

	company = test_company()
	if frappe.db.exists("Sign Profile", company):
		frappe.throw(f"Sign Profile {company} exists already; the e2e run expects none")
	return {"company": company, "started": str(now_datetime())}


def purge_certificates(started: str) -> dict:
	"""Delete the profiles and certificates created since `started`, with their files and passwords."""
	require_test_site()
	since = get_datetime(started)
	profiles = frappe.get_all("Sign Profile", filters={"creation": [">=", since]}, pluck="name")
	certificates = frappe.get_all("Sign Certificate", filters={"creation": [">=", since]}, pluck="name")
	frappe.db.delete("Sign Profile", {"name": ["in", profiles or [""]]})
	frappe.db.delete("Sign Certificate", {"name": ["in", certificates or [""]]})
	frappe.db.delete("__Auth", {"doctype": "Sign Certificate", "name": ["in", certificates or [""]]})
	purge_since(since)
	return {"profiles": profiles, "certificates": certificates}
