"""Stage 6: PAdES-B-LT seal with a Signer, RFC 3161 timestamp and revocation info (D3).

The seal is one approval signature over the final PDF (values and certificate pages included).
pyHanko adds the signature timestamp (B-T) and stores the chain, CRLs and OCSP responses in the
Document Security Store (B-LT), so the seal can be checked after the certificates expire.
"""

from __future__ import annotations

import asyncio
import io

from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
from pyhanko.pdf_utils.misc import PdfError as PyhankoPdfError
from pyhanko.sign import fields, signers
from pyhanko.sign.general import SigningError
from pyhanko.sign.timestamps import TimeStamper, TimestampRequestError
from pyhanko_certvalidator import ValidationContext
from pyhanko_certvalidator.errors import PathBuildingError, PathValidationError

from frappe_sign.crypto.signer import Signer, SignerError
from frappe_sign.crypto.tsa import FallbackTimeStamper
from frappe_sign.pdf.types import SealError

SEAL_FIELD = "FrappeSignSeal"
SEAL_ERRORS = (
	SignerError,
	SigningError,
	TimestampRequestError,
	PyhankoPdfError,
	PathBuildingError,
	PathValidationError,
	OSError,
	ValueError,
)


def seal_pdf(
	pdf: bytes,
	*,
	signer: Signer,
	tsa_urls: list[str],
	reason: str,
	location: str,
	contact: str,
	timestamper: TimeStamper | None = None,
	validation_context: ValidationContext | None = None,
) -> bytes:
	"""Seal `pdf` as PAdES-B-LT.

	`timestamper` and `validation_context` default to the TSA URLs and to fetching revocation
	data online; tests pass offline ones.
	"""
	try:
		if timestamper is None:
			if not tsa_urls:
				raise SealError("A TSA URL is required to seal")
			timestamper = FallbackTimeStamper(tsa_urls)
		pyhanko_signer = signer.pyhanko_signer()
		context = validation_context or online_validation_context(pyhanko_signer)
		metadata = signers.PdfSignatureMetadata(
			field_name=SEAL_FIELD,
			md_algorithm="sha256",
			subfilter=fields.SigSeedSubFilter.PADES,
			embed_validation_info=True,
			use_pades_lta=False,
			validation_context=context,
			reason=reason,
			location=location,
			contact_info=contact,
		)
		writer = IncrementalPdfFileWriter(io.BytesIO(pdf), strict=False)
		pdf_signer = signers.PdfSigner(metadata, signer=pyhanko_signer, timestamper=timestamper)
		output = asyncio.run(pdf_signer.async_sign_pdf(writer, in_place=False))
	except SealError:
		raise
	except SEAL_ERRORS as error:
		raise SealError(f"Sealing failed: {error}") from error
	return bytes(output.getbuffer())


def online_validation_context(pyhanko_signer: signers.Signer) -> ValidationContext:
	"""Fetch CRLs and OCSP responses for the chain. Self-signed roots shipped in the PKCS#12
	(a company's own CA) are trusted on top of the system store."""
	chain = list(pyhanko_signer.cert_registry)
	own_roots = [cert for cert in chain if cert.self_signed]
	return ValidationContext(
		extra_trust_roots=own_roots,
		other_certs=chain,
		allow_fetching=True,
		revocation_mode="soft-fail",
	)
