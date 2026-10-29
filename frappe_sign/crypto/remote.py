"""RemoteSigner (D16, P3.6): a signing key that never leaves an HSM or a trust service.

- PKCS#11: a hardware or software token (a smart card, a network HSM, SoftHSM in tests), through
  pyHanko's PKCS#11 signer. The session is open only while the seal signs.
- CSC: a Cloud Signature Consortium service (v1 API): `credentials/info` for the certificates,
  `credentials/authorize` with the PIN for each seal, `signatures/signHash` for the signature.

The PIN and the access token are passed in by the service (from Password fields); they are never
logged, never in `repr` and never in an error message.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

import aiohttp
from asn1crypto import x509
from pkcs11 import PKCS11Error
from pyhanko.config.pkcs11 import PKCS11SignatureConfig, TokenCriteria
from pyhanko.sign import signers
from pyhanko.sign.general import SigningError
from pyhanko.sign.pkcs11 import PKCS11SigningContext
from pyhanko.sign.signers.csc_signer import (
	CSCAuthorizationInfo,
	CSCAuthorizationManager,
	CSCCredentialInfo,
	CSCServiceSessionInfo,
	CSCSigner,
	fetch_certs_in_csc_credential,
)

from frappe_sign.crypto.signer import SignerError

PKCS11, CSC = "pkcs11", "csc"

# What a token, a library or a service can raise before a signature exists.
REMOTE_ERRORS = (PKCS11Error, SigningError, aiohttp.ClientError, TimeoutError, OSError, RuntimeError)


class RemoteSigner:
	def __init__(self, config: dict[str, Any], pin: str | None = None, token: str | None = None) -> None:
		"""`config` is already validated (utils/remote_config.parse_config): crypto/ imports no utils."""
		self._config = dict(config)
		self._pin = pin
		self._token = token

	def __repr__(self) -> str:
		return f"RemoteSigner({self._config.get('type')}, <secrets hidden>)"

	@asynccontextmanager
	async def open(self) -> AsyncIterator[signers.Signer]:
		opener = self._open_pkcs11 if self._config.get("type") == PKCS11 else self._open_csc
		try:
			async with opener() as signer:
				require_valid_now(signer.signing_cert, datetime.now(UTC))
				yield signer
		except KeyError as error:
			raise SignerError(f"The remote signing settings are incomplete: {error}") from error
		except REMOTE_ERRORS as error:
			# The message never holds the PIN: pyHanko and python-pkcs11 do not put it there.
			raise SignerError(f"Remote signing failed: {type(error).__name__}: {error}") from error

	def chain(self) -> list[x509.Certificate]:
		async def read() -> list[x509.Certificate]:
			async with self.open() as signer:
				# The signing certificate first; the registry may or may not hold it.
				found = {cert.dump(): cert for cert in (signer.signing_cert, *signer.cert_registry)}
				return list(found.values())

		return asyncio.run(read())

	@asynccontextmanager
	async def _open_pkcs11(self) -> AsyncIterator[signers.Signer]:
		config = self._config
		label = config.get("token_label")
		context = PKCS11SigningContext(
			PKCS11SignatureConfig(
				module_path=config["module_path"],
				token_criteria=TokenCriteria(label=label) if label else None,
				slot_no=config.get("slot_no"),
				key_label=config.get("key_label") or config.get("cert_label"),
				cert_label=config.get("cert_label") or config.get("key_label"),
				user_pin=self._pin,
			)
		)
		# A sync `with`, not `async with`: pyHanko's async enter leaks the logged-in session when the
		# key is not found, and the next login then fails with UserAlreadyLoggedIn.
		with context as signer:
			await signer.ensure_objects_loaded()
			yield signer

	@asynccontextmanager
	async def _open_csc(self) -> AsyncIterator[signers.Signer]:
		config = self._config
		info = CSCServiceSessionInfo(
			service_url=config["service_url"].rstrip("/"),
			credential_id=config["credential_id"],
			oauth_token=self._token,
			api_ver=config.get("api_version", "v1"),
		)
		async with aiohttp.ClientSession() as session:
			try:
				credential = await fetch_certs_in_csc_credential(session, info)
			except (IndexError, KeyError, TypeError) as error:
				raise SignerError("The signing service returned no usable certificate") from error
			manager = PinAuthorization(info, credential, session, self._pin)
			yield CSCSigner(session, manager)


class PinAuthorization(CSCAuthorizationManager):
	"""Ask `credentials/authorize` for signature activation data with the PIN, once per signing."""

	def __init__(
		self,
		info: CSCServiceSessionInfo,
		credential: CSCCredentialInfo,
		session: aiohttp.ClientSession,
		pin: str | None,
	) -> None:
		super().__init__(info, credential)
		self._session = session
		self._pin = pin

	async def authorize_signature(self, hash_b64s: list[str]) -> CSCAuthorizationInfo:
		pinned = self.credential_info.hash_pinning_required
		url = self.csc_session_info.endpoint_url("credentials/authorize")  # type: ignore[no-untyped-call]
		request = self.format_csc_auth_request(pin=self._pin, hash_b64s=hash_b64s if pinned else None)
		try:
			async with self._session.post(
				url,
				headers=self.auth_headers,
				json=request,
				raise_for_status=True,
				timeout=aiohttp.ClientTimeout(total=30),
			) as response:
				return self.parse_csc_auth_response(await response.json())
		except aiohttp.ClientError as error:
			raise SigningError("The signing service refused to authorize the signature") from error


def require_valid_now(certificate: x509.Certificate, now: datetime) -> None:
	"""The certificate is valid now, as Pkcs12Signer checks before each seal."""
	if certificate.not_valid_before > now:
		raise SignerError("The remote signing certificate is not valid yet.")
	if certificate.not_valid_after < now:
		raise SignerError("The remote signing certificate has expired.")


__all__ = ["CSC", "PKCS11", "RemoteSigner", "require_valid_now"]
