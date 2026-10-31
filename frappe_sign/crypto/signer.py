"""Signer protocol, Pkcs12Signer (Phase 1) and, in crypto/remote.py, RemoteSigner (Phase 3, D16).

A Signer opens a ready pyHanko signer inside the seal's event loop (`open`), so a remote signer can
hold a token session or an HTTP session only while it signs. Services decrypt the key material (the
certificate password through get_password) and pass bytes in; crypto/ never touches DocTypes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from asn1crypto import x509
from pyhanko.sign import signers

from frappe_sign.crypto.pkcs12 import Pkcs12Error, inspect, require_usable


class SignerError(Exception):
	"""The key material cannot sign: wrong password or PIN, no key, or the certificate is not valid now."""


@runtime_checkable
class Signer(Protocol):
	def open(self) -> AbstractAsyncContextManager[signers.Signer]:
		"""A pyHanko signer, valid inside the `async with`. Raises SignerError when it cannot sign."""
		...

	def chain(self) -> list[x509.Certificate]:
		"""The signing certificate and its chain, without signing anything."""
		...


class Pkcs12Signer:
	def __init__(self, p12: bytes, password: bytes) -> None:
		self._p12 = p12
		self._password = password
		self._signer: signers.SimpleSigner | None = None

	def __repr__(self) -> str:
		return "Pkcs12Signer(<PKCS#12 key material>)"

	@asynccontextmanager
	async def open(self) -> AsyncIterator[signers.Signer]:
		yield self.pyhanko_signer()

	def chain(self) -> list[x509.Certificate]:
		signer = self.pyhanko_signer()
		found = {cert.dump(): cert for cert in (signer.signing_cert, *signer.cert_registry)}
		return list(found.values())

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
