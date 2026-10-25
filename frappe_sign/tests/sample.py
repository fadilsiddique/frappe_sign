"""Make tests/output/sample_signed.pdf for the Gate 1 Adobe Reader check.

    bench --site sign.localhost execute frappe_sign.tests.sample.make_sample_signed_pdf

Runs the real flow on a test site (allow_tests): template, envelope, two signers (one with an Arabic
name), intermediate PDFs, then the seal job. The seal uses the test sealing certificate (trust
tests/fixtures/certs/root_ca.pem in Adobe) and, when the network allows, a public RFC 3161 TSA
(DigiCert, then Sectigo) with its revocation data fetched online; otherwise the in-process test TSA.
Everything it creates is deleted afterwards; only the PDF stays.
"""

from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.utils import get_datetime, now_datetime
from pyhanko.sign.timestamps import TimestampRequestError
from pyhanko_certvalidator import ValidationContext

from frappe_sign.crypto.tsa import DEFAULT_TSA_URLS, FallbackTimeStamper
from frappe_sign.services import sealing, signing
from frappe_sign.services import verify as verify_service
from frappe_sign.tests import pki
from frappe_sign.tests.cleanup import purge_envelope, purge_profile, purge_since, purge_template
from frappe_sign.tests.e2e import require_test_site
from frappe_sign.tests.factories import make_email_account, make_profile, signature_field, test_company
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now
from frappe_sign.tests.unit.test_overlay import signature_png
from frappe_sign.utils.files import read_file
from frappe_sign.utils.request import Client
from frappe_sign.utils.users import run_as

OUTPUT = Path(__file__).resolve().parent / "output" / "sample_signed.pdf"
MADE_UP_COMPANY = "Upscape Sample Co"


def public_timestamper():
	"""A public TSA when reachable, else the in-process test TSA."""
	stamper = FallbackTimeStamper(list(DEFAULT_TSA_URLS))
	try:
		import asyncio

		asyncio.run(stamper.async_timestamp(b"\x00" * 32, "sha256"))
		return stamper, "public TSA (" + ", ".join(DEFAULT_TSA_URLS) + ")"
	except (TimestampRequestError, OSError):
		return pki.timestamper(), "test TSA (offline)"


def validate_with_system_roots(pdf: bytes):
	"""PAdES-B-LT validation from the embedded data only, trusting the test root and the system store
	(a public TSA chains to the system store)."""
	import io

	from pyhanko.pdf_utils.reader import PdfFileReader
	from pyhanko.sign.validation import RevocationInfoValidationType, validate_pdf_ltv_signature

	signature = PdfFileReader(io.BytesIO(pdf)).embedded_signatures[0]
	return validate_pdf_ltv_signature(
		signature,
		RevocationInfoValidationType.PADES_LT,
		validation_context_kwargs={
			"extra_trust_roots": [pki.root_cert()],
			"allow_fetching": False,
			"retroactive_revinfo": True,
			"revocation_mode": "soft-fail",
		},
	)


def sample_fields() -> list[dict]:
	return [
		signature_field(x=0.08, y=0.62, w=0.36, h=0.08),
		signature_field(field_key="customer_name", field_type="Full Name", x=0.08, y=0.71, w=0.36, h=0.03),
		signature_field(field_key="customer_date", field_type="Date Signed", x=0.08, y=0.75, w=0.36, h=0.03),
		signature_field(field_key="company_signature", role_label="Company", x=0.56, y=0.62, w=0.36, h=0.08),
		signature_field(
			field_key="company_name",
			role_label="Company",
			field_type="Full Name",
			x=0.56,
			y=0.71,
			w=0.36,
			h=0.03,
		),
		signature_field(
			field_key="company_date",
			role_label="Company",
			field_type="Date Signed",
			x=0.56,
			y=0.75,
			w=0.36,
			h=0.03,
		),
	]


def make_sample_signed_pdf(keep: bool = False) -> dict:
	"""`keep` leaves the envelope in place (for trying `bench frappe-sign verify`); purge it with
	frappe_sign.tests.e2e.purge_created and the returned `started`."""
	require_test_site()
	started = now_datetime()
	envelope = None
	try:
		with run_as("Administrator"):
			make_email_account(skip_smtp_check=True)
			make_profile(
				test_company(MADE_UP_COMPANY),
				legal_footer="Sample only. Sealed with the Frappe Sign test certificate.",
			)
			version = publish_template(fields=sample_fields(), pdf="arabic_text.pdf")
			draft = make_draft(
				version,
				recipients=[
					{"role_label": "Customer", "full_name": "أحمد خان", "email": "ahmed@example.com"},
					{"role_label": "Company", "full_name": "Fatima Ali", "email": "fatima@example.com"},
				],
				title="Sample Service Agreement",
				company=test_company(MADE_UP_COMPANY),
			)
			envelope = draft.name
			with capture_tokens() as box, patch("frappe.enqueue"):
				send_now(envelope)
				for role, key in (("Customer", "customer_signature"), ("Company", "company_signature")):
					row = next(
						r
						for r in frappe.get_doc("Sign Envelope", envelope).recipients
						if r.role_label == role
					)
					client = Client(ip="203.0.113.20", user_agent="Frappe Sign sample")
					opened = signing.open(box[row.name], client)
					signing.consent(opened["session"], opened["consent"]["version"], client)
					signing.save_capture(opened["session"], key, "Draw", signature_png(), client=client)
					signing.finish(opened["session"], client)
			timestamper, tsa = public_timestamper()
			context = ValidationContext(
				extra_trust_roots=[pki.root_cert()],
				crls=[pki.root_crl()],
				allow_fetching=True,
				revocation_mode="soft-fail",
			)
			options = {"timestamper": timestamper, "validation_context": context}
			with patch.object(sealing, "seal_options", return_value=options), patch("frappe.enqueue"):
				if not sealing.begin(envelope):
					frappe.throw(frappe._("The sample envelope was not ready to seal."))
				sealing.run(envelope)
			doc = frappe.get_doc("Sign Envelope", envelope)
			sealed = read_file(doc.signed_file)
			OUTPUT.parent.mkdir(exist_ok=True)
			OUTPUT.write_bytes(sealed)
			check = verify_service.check_envelope(envelope)
			status = validate_with_system_roots(sealed)
			return {
				"envelope": envelope,
				"started": str(started),
				"output": str(OUTPUT),
				"bytes": len(sealed),
				"tsa": tsa,
				"envelope_check": "OK" if check.ok else check.problems,
				"pades_lt_valid": bool(status.bottom_line),
				"timestamp": str(status.timestamp_validity.timestamp) if status.timestamp_validity else None,
				"signed_sha256": doc.signed_sha256,
			}
	finally:
		if keep:
			frappe.db.commit()  # nosemgrep: frappe-manual-commit (keeps the sample for trying verify)
		else:
			purge_sample(envelope, str(started))


def purge_sample(envelope: str | None, started: str) -> None:
	"""Delete a sample made with keep=True (or left behind by a failed run)."""
	require_test_site()
	frappe.db.rollback()
	for template in purge_envelope(envelope):
		purge_template(template)
	purge_profile(test_company(MADE_UP_COMPANY))
	purge_since(get_datetime(started))
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (removes the sample data it committed)
