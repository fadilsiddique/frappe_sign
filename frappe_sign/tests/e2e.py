"""Fixtures for the Playwright tests in e2e/. Run through `bench execute`, which commits.

    bench --site sign.localhost execute frappe_sign.tests.e2e.create_guest_envelope
    bench --site sign.localhost execute frappe_sign.tests.e2e.purge --kwargs '{"envelope": "...", "started": "..."}'

Both refuse to run unless the site has allow_tests set, so they never touch a working site.
"""

import frappe
from frappe.utils import get_datetime, now_datetime

from frappe_sign.tests.cleanup import purge_envelope, purge_since, purge_template
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
