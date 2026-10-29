"""Verification (DESIGN 5.5, 5.6): the audit chain, file hashes and the PAdES seal.

Used by the public /sign-verify API and by `bench frappe-sign verify`. Anonymous answers never show
document content: a matching file shows signers and times, an envelope ID alone shows only status.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import frappe
from pyhanko_certvalidator import ValidationContext

from frappe_sign.pdf.seal import inspect_seal
from frappe_sign.services import audit, sealing
from frappe_sign.utils.dates import format_local
from frappe_sign.utils.files import read_file
from frappe_sign.utils.hashing import sha256_hex


@dataclass
class EnvelopeCheck:
	"""Full check of one envelope for the bench command."""

	envelope: str
	ok: bool
	chain_ok: bool
	events: int
	first_bad_seq: int | None = None
	chain_reason: str | None = None
	problems: list[str] = field(default_factory=list)
	seal_trusted: bool | None = None


def check_envelope(name: str) -> EnvelopeCheck:
	"""Recompute the chain and the file hashes (original, intermediates, signed)."""
	doc = frappe.get_doc("Sign Envelope", name)
	report = audit.verify_chain(name)
	problems = []
	if not report.ok:
		problems.append(f"Audit chain breaks at event {report.first_bad_seq}: {report.reason}")
	files = [
		("original", doc.original_file, doc.original_sha256),
		("signed", doc.signed_file, doc.signed_sha256),
	]
	files += [
		(f"intermediate of {row.full_name}", row.intermediate_file, row.intermediate_sha256)
		for row in doc.recipients
	]
	for label, file_name, expected in files:
		if not file_name:
			continue
		try:
			actual = sha256_hex(read_file(file_name))
		except (frappe.DoesNotExistError, OSError):
			problems.append(f"The {label} PDF is missing")
			continue
		if actual != expected:
			problems.append(f"The {label} PDF does not match its recorded SHA-256")
	if doc.audit_head and doc.audit_head not in frappe.get_all(
		"Sign Event", filters={"envelope": name}, pluck="hash"
	):
		problems.append("The audit head printed on the certificate is not in the chain")
	seal_trusted = None
	if doc.signed_file and not problems:
		seal = inspect_seal(read_file(doc.signed_file), trust_context(name))
		seal_trusted = seal.trusted
		if not (seal.intact and seal.valid):
			problems.append(f"The seal does not validate: {seal.error or 'signature not intact'}")
	return EnvelopeCheck(
		envelope=name,
		ok=not problems,
		chain_ok=report.ok,
		events=report.count,
		first_bad_seq=report.first_bad_seq,
		chain_reason=report.reason,
		problems=problems,
		seal_trusted=seal_trusted,
	)


def verify_public(content: bytes | None = None, envelope: str | None = None) -> dict[str, Any]:
	"""/sign-verify: a PDF (matched by hash) and/or an envelope ID."""
	result: dict[str, Any] = {"found": False}
	if content:
		digest = sha256_hex(content)
		name = frappe.db.get_value("Sign Envelope", {"signed_sha256": digest}, "name")
		result["sha256"] = digest
		result["seal"] = asdict(inspect_seal(content, trust_context(name)))
		if name and (not envelope or envelope == name):
			return result | {"found": True, "matches": True} | envelope_details(name, with_signers=True)
		if envelope:
			result["matches"] = False
	if envelope and frappe.db.exists("Sign Envelope", envelope):
		result |= {"found": True} | envelope_details(envelope, with_signers=False)
	return result


def envelope_details(name: str, *, with_signers: bool) -> dict[str, Any]:
	doc = frappe.get_doc("Sign Envelope", name)
	details: dict[str, Any] = {
		"envelope": name,
		"status": doc.status,
		"sealed": doc.sealing_state == "Sealed",
		"completed_on": format_local(doc.completed_on),
	}
	if with_signers:
		details["signers"] = [
			{"name": row.full_name, "role": row.role_label, "signed_on": format_local(row.signed_on)}
			for row in doc.recipients
			if row.status == "Signed"
		]
	return details


def trust_context(envelope: str | None) -> ValidationContext:
	"""Trust the self-signed roots of the envelope's own sealing certificate, plus the system store."""
	roots = []
	if envelope:
		company = frappe.db.get_value("Sign Envelope", envelope, "company")
		try:
			signer = sealing.sealing_signer(company)
			roots = [cert for cert in signer.chain() if cert.self_signed]
		except Exception:
			# Verification still reports integrity when the certificate is gone or unreadable.
			frappe.log_error(
				title="Frappe Sign: verify trust roots",
				reference_doctype="Sign Envelope",
				reference_name=envelope,
			)
	return ValidationContext(extra_trust_roots=roots, allow_fetching=False, revocation_mode="soft-fail")
