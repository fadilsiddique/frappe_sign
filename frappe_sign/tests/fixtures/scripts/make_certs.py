"""Generate the test PKI in tests/fixtures/certs/: a self-signed root CA, sealing certificates and a TSA.

Run from the bench directory:

    env/bin/python apps/frappe_sign/frappe_sign/tests/fixtures/scripts/make_certs.py

Keys are random on every run; names, serials, dates and passwords are fixed, so the files are
equivalent each time. These keys are public test material: never trust this CA outside tests.
"""

import sys
from datetime import UTC, datetime
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

CERTS_DIR = Path(__file__).resolve().parents[1] / "certs"

P12_PASSWORD = b"fixture-seal"
CRL_URL = "http://crl.frappe-sign.test/root.crl"
ORGANIZATION = "Frappe Sign Tests"

CA_VALIDITY = (datetime(2026, 1, 1, tzinfo=UTC), datetime(2046, 1, 1, tzinfo=UTC))
LEAF_VALIDITY = (datetime(2026, 1, 1, tzinfo=UTC), datetime(2041, 1, 1, tzinfo=UTC))
EXPIRED_VALIDITY = (datetime(2020, 1, 1, tzinfo=UTC), datetime(2021, 1, 1, tzinfo=UTC))


def name(common_name: str) -> x509.Name:
	return x509.Name(
		[
			x509.NameAttribute(NameOID.COUNTRY_NAME, "AE"),
			x509.NameAttribute(NameOID.ORGANIZATION_NAME, ORGANIZATION),
			x509.NameAttribute(NameOID.COMMON_NAME, common_name),
		]
	)


def new_key() -> rsa.RSAPrivateKey:
	return rsa.generate_private_key(public_exponent=65537, key_size=3072)


def key_usage(**enabled: bool) -> x509.KeyUsage:
	flags = dict.fromkeys(
		(
			"digital_signature",
			"content_commitment",
			"key_encipherment",
			"data_encipherment",
			"key_agreement",
			"key_cert_sign",
			"crl_sign",
			"encipher_only",
			"decipher_only",
		),
		False,
	)
	return x509.KeyUsage(**{**flags, **enabled})


def make_root(key: rsa.RSAPrivateKey) -> x509.Certificate:
	subject = name("Frappe Sign Test Root CA")
	return (
		x509.CertificateBuilder()
		.subject_name(subject)
		.issuer_name(subject)
		.public_key(key.public_key())
		.serial_number(1)
		.not_valid_before(CA_VALIDITY[0])
		.not_valid_after(CA_VALIDITY[1])
		.add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
		.add_extension(key_usage(key_cert_sign=True, crl_sign=True), critical=True)
		.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
		.sign(key, hashes.SHA256())
	)


def issue(
	ca_key: rsa.RSAPrivateKey,
	ca_cert: x509.Certificate,
	key: rsa.RSAPrivateKey,
	common_name: str,
	serial: int,
	validity: tuple[datetime, datetime],
	extended_usage: x509.ExtendedKeyUsage | None = None,
) -> x509.Certificate:
	builder = (
		x509.CertificateBuilder()
		.subject_name(name(common_name))
		.issuer_name(ca_cert.subject)
		.public_key(key.public_key())
		.serial_number(serial)
		.not_valid_before(validity[0])
		.not_valid_after(validity[1])
		.add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
		.add_extension(key_usage(digital_signature=True, content_commitment=True), critical=True)
		.add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
		.add_extension(
			x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False
		)
		.add_extension(
			x509.CRLDistributionPoints(
				[x509.DistributionPoint([x509.UniformResourceIdentifier(CRL_URL)], None, None, None)]
			),
			critical=False,
		)
	)
	if extended_usage:
		builder = builder.add_extension(extended_usage, critical=True)
	return builder.sign(ca_key, hashes.SHA256())


def make_crl(ca_key: rsa.RSAPrivateKey, ca_cert: x509.Certificate) -> x509.CertificateRevocationList:
	"""An empty CRL, so tests can supply revocation data without fetching CRL_URL."""
	return (
		x509.CertificateRevocationListBuilder()
		.issuer_name(ca_cert.subject)
		.last_update(CA_VALIDITY[0])
		.next_update(CA_VALIDITY[1])
		.add_extension(x509.CRLNumber(1), critical=False)
		.sign(ca_key, hashes.SHA256())
	)


def pem_key(key: rsa.RSAPrivateKey) -> bytes:
	return key.private_bytes(
		serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
	)


def p12(
	label: bytes, key: rsa.RSAPrivateKey | None, cert: x509.Certificate, ca_cert: x509.Certificate
) -> bytes:
	return pkcs12.serialize_key_and_certificates(
		label, key, cert, [ca_cert], serialization.BestAvailableEncryption(P12_PASSWORD)
	)


def generate(out_dir: Path = CERTS_DIR) -> None:
	out_dir.mkdir(parents=True, exist_ok=True)
	ca_key = new_key()
	ca_cert = make_root(ca_key)

	seal_key = new_key()
	seal_cert = issue(ca_key, ca_cert, seal_key, "Frappe Sign Test Seal", 2, LEAF_VALIDITY)
	expired_key = new_key()
	expired_cert = issue(ca_key, ca_cert, expired_key, "Frappe Sign Expired Seal", 3, EXPIRED_VALIDITY)
	tsa_key = new_key()
	tsa_cert = issue(
		ca_key,
		ca_cert,
		tsa_key,
		"Frappe Sign Test TSA",
		4,
		LEAF_VALIDITY,
		x509.ExtendedKeyUsage([ExtendedKeyUsageOID.TIME_STAMPING]),
	)

	files = {
		"root_ca.pem": ca_cert.public_bytes(serialization.Encoding.PEM),
		"root_ca.key.pem": pem_key(ca_key),
		"root_ca.crl": make_crl(ca_key, ca_cert).public_bytes(serialization.Encoding.DER),
		"sealing.p12": p12(b"Frappe Sign Test Seal", seal_key, seal_cert, ca_cert),
		"sealing_expired.p12": p12(b"Frappe Sign Expired Seal", expired_key, expired_cert, ca_cert),
		"sealing_no_key.p12": p12(b"Frappe Sign Test Seal", None, seal_cert, ca_cert),
		"tsa.pem": tsa_cert.public_bytes(serialization.Encoding.PEM),
		"tsa.key.pem": pem_key(tsa_key),
	}
	for filename, content in files.items():
		(out_dir / filename).write_bytes(content)


if __name__ == "__main__":
	target = Path(sys.argv[1]) if len(sys.argv) > 1 else CERTS_DIR
	generate(target)
	print(f"Test PKI written to {target}")
