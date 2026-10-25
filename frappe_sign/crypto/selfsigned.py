"""Self-signed sealing certificates, for trials and pilots (the "Create test certificate" button).

A self-signed certificate seals and shows any later change, but Adobe Reader shows the identity as
unknown because nobody vouches for it. Production sites use a CA-issued or AATL certificate.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID

KEY_SIZE = 3072
MAX_YEARS = 10
# Start a little in the past, so a server clock that runs slow still accepts the certificate.
CLOCK_SKEW = timedelta(minutes=5)


@dataclass(frozen=True)
class SelfSigned:
	p12: bytes
	password: str

	def __repr__(self) -> str:
		return "SelfSigned(<PKCS#12 key material>)"


def make_self_signed(
	common_name: str, organization: str | None = None, years: int = 3, now: datetime | None = None
) -> SelfSigned:
	"""A new RSA key and a self-signed certificate for it, in a PKCS#12 file with a random password."""
	common_name = common_name.strip()
	if not common_name:
		raise ValueError("A common name is required")
	if not 1 <= years <= MAX_YEARS:
		raise ValueError(f"Validity must be 1 to {MAX_YEARS} years")
	now = now or datetime.now(UTC)
	key = rsa.generate_private_key(public_exponent=65537, key_size=KEY_SIZE)
	attributes = [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
	if organization and organization.strip():
		attributes.append(x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization.strip()))
	subject = x509.Name(attributes)
	certificate = (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(subject)
		.public_key(key.public_key())
		.serial_number(x509.random_serial_number())
		.not_valid_before(now - CLOCK_SKEW)
		.not_valid_after(now + timedelta(days=365 * years))
		.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
		.add_extension(signing_key_usage(), critical=True)
		.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
		.sign(key, hashes.SHA256())
	)
	password = secrets.token_urlsafe(24)
	p12 = pkcs12.serialize_key_and_certificates(
		name=common_name.encode(),
		key=key,
		cert=certificate,
		cas=None,
		encryption_algorithm=BestAvailableEncryption(password.encode()),
	)
	return SelfSigned(p12=p12, password=password)


def signing_key_usage() -> x509.KeyUsage:
	"""Digital signature and non-repudiation (content commitment): what pyHanko and Adobe expect."""
	return x509.KeyUsage(
		digital_signature=True,
		content_commitment=True,
		key_encipherment=False,
		data_encipherment=False,
		key_agreement=False,
		key_cert_sign=False,
		crl_sign=False,
		encipher_only=False,
		decipher_only=False,
	)
