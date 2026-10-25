"""Signer protocol, Pkcs12Signer (Phase 1) and RemoteSigner (Phase 3) (D16).

A Signer hands pdf/seal.py a ready pyHanko signer. Services decrypt the key material (the
certificate password through get_password) and pass bytes in; crypto/ never touches DocTypes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pyhanko.sign import signers

from frappe_sign.crypto.pkcs12 import Pkcs12Error, inspect, require_usable


class SignerError(Exception):
	"""The key material cannot sign: wrong password, no key, or the certificate is not valid now."""


@runtime_checkable
class Signer(Protocol):
	def pyhanko_signer(self) -> signers.Signer: ...


class Pkcs12Signer:
	def __init__(self, p12: bytes, password: bytes) -> None:
		self._p12 = p12
		self._password = password
		self._signer: signers.SimpleSigner | None = None

	def __repr__(self) -> str:
		return "Pkcs12Signer(<PKCS#12 key material>)"

	def pyhanko_signer(self) -> signers.SimpleSigner:
		if self._signer is None:
			self._signer = self._load()
		return self._signer

	def _load(self) -> signers.SimpleSigner:
		try:
			require_usable(inspect(self._p12, self._password), now=datetime.now(UTC).replace(tzinfo=None))
		except Pkcs12Error as error:
			raise SignerError(str(error)) from error
		signer: signers.SimpleSigner | None = signers.SimpleSigner.load_pkcs12_data(
			self._p12, [], passphrase=self._password
		)
		if signer is None:
			raise SignerError("pyHanko could not load the PKCS#12 key material")
		return signer
