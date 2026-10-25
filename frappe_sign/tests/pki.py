"""The test PKI (tests/fixtures/certs/) as pyHanko objects, for sealing offline.

The in-process timestamper signs with tsa.pem, and the validation context carries the root's
CRL, so neither sealing nor validation needs the network.
"""

import io
from pathlib import Path

from pyhanko.keys import load_cert_from_pemder, load_private_key_from_pemder
from pyhanko.pdf_utils.reader import PdfFileReader
from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper
from pyhanko.sign.validation import RevocationInfoValidationType, validate_pdf_ltv_signature
from pyhanko.sign.validation.status import PdfSignatureStatus
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.registry import SimpleCertificateStore

from frappe_sign.crypto.signer import Pkcs12Signer

CERTS = Path(__file__).resolve().parent / "fixtures" / "certs"
P12_PASSWORD = b"fixture-seal"


def root_cert():
	return load_cert_from_pemder(str(CERTS / "root_ca.pem"))


def root_crl() -> bytes:
	return (CERTS / "root_ca.crl").read_bytes()


def sealing_signer(name: str = "sealing.p12") -> Pkcs12Signer:
	return Pkcs12Signer((CERTS / name).read_bytes(), P12_PASSWORD)


def timestamper() -> DummyTimeStamper:
	return DummyTimeStamper(
		tsa_cert=load_cert_from_pemder(str(CERTS / "tsa.pem")),
		tsa_key=load_private_key_from_pemder(str(CERTS / "tsa.key.pem"), None),
		certs_to_embed=SimpleCertificateStore.from_certs([root_cert()]),
	)


def sealing_validation_context() -> ValidationContext:
	"""What the seal job would fetch: the root as trust anchor and its CRL."""
	return ValidationContext(
		trust_roots=[root_cert()], crls=[root_crl()], allow_fetching=False, revocation_mode="hard-fail"
	)


def validate_lt(pdf: bytes) -> PdfSignatureStatus:
	"""Validate the seal as PAdES-B-LT, using only the revocation data embedded in the PDF.

	The fixture CRL was issued before the seal, so revocation data is accepted retroactively.
	A real CA issues fresh CRLs and OCSP responses, which pyHanko accepts without that flag.
	"""
	signature = PdfFileReader(io.BytesIO(pdf)).embedded_signatures[0]
	return validate_pdf_ltv_signature(
		signature,
		RevocationInfoValidationType.PADES_LT,
		validation_context_kwargs={
			"trust_roots": [root_cert()],
			# pyHanko fetches by default here; the test domains do not resolve.
			"allow_fetching": False,
			"retroactive_revinfo": True,
			"revocation_mode": "soft-fail",
		},
	)
