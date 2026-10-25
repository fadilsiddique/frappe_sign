"""Inspect PKCS#12 files: subject, issuer, validity, fingerprint. Used by the Sign Certificate controller."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.serialization import pkcs12


class Pkcs12Error(Exception):
	"""`reason` is one of wrong_password, no_key, no_certificate, expired, not_yet_valid."""

	def __init__(self, reason: str, message: str) -> None:
		super().__init__(message)
		self.reason = reason


@dataclass(frozen=True)
class Pkcs12Info:
	subject: str
	issuer: str
	# Naive UTC, as Frappe stores Datetime fields.
	valid_from: datetime
	valid_to: datetime
	fingerprint_sha256: str
	has_key: bool


def inspect(p12: bytes, password: bytes) -> Pkcs12Info:
	try:
		key, cert, extra = pkcs12.load_key_and_certificates(p12, password)
	except ValueError as error:
		raise Pkcs12Error("wrong_password", "Wrong password, or not a PKCS#12 file") from error
	if cert is None:
		# Without a key, the leaf is stored as one more certificate; take the one no other names as issuer.
		cert = leaf_of(extra)
	return Pkcs12Info(
		subject=cert.subject.rfc4514_string(),
		issuer=cert.issuer.rfc4514_string(),
		valid_from=cert.not_valid_before_utc.replace(tzinfo=None),
		valid_to=cert.not_valid_after_utc.replace(tzinfo=None),
		fingerprint_sha256=cert.fingerprint(hashes.SHA256()).hex(),
		has_key=key is not None,
	)


def leaf_of(certs: list[x509.Certificate]) -> x509.Certificate:
	issuers = {cert.issuer for cert in certs}
	leaves = [cert for cert in certs if cert.subject not in issuers or cert.subject == cert.issuer]
	leaves = [cert for cert in leaves if cert.subject != cert.issuer] or leaves
	if not leaves:
		raise Pkcs12Error("no_certificate", "The PKCS#12 file holds no certificate")
	return leaves[0]


def require_usable(info: Pkcs12Info, now: datetime) -> None:
	"""A sealing certificate needs its private key and must be valid at `now` (naive UTC)."""
	if not info.has_key:
		raise Pkcs12Error("no_key", "The PKCS#12 file holds no private key")
	if now < info.valid_from:
		raise Pkcs12Error("not_yet_valid", f"The certificate is valid from {info.valid_from:%Y-%m-%d}")
	if now > info.valid_to:
		raise Pkcs12Error("expired", f"The certificate expired on {info.valid_to:%Y-%m-%d}")
