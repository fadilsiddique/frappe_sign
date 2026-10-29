"""RFC 3161 timestamp client that tries each TSA URL in order (DESIGN 5.3)."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from collections.abc import Callable, Iterable

from asn1crypto import algos, tsp
from pyhanko.sign.timestamps import HTTPTimeStamper, TimeStamper, TimestampRequestError

TIMEOUT_SECONDS = 10
# Used when Sign Settings lists no TSA. Both are free, public RFC 3161 services.
DEFAULT_TSA_URLS = ("http://timestamp.digicert.com", "http://timestamp.sectigo.com")
GRANTED = ("granted", "granted_with_mods")

TimeStamperFactory = Callable[[str, int], TimeStamper]


def http_timestamper(url: str, timeout: int) -> TimeStamper:
	return HTTPTimeStamper(url, timeout=timeout)  # type: ignore[no-untyped-call]


def tsa_urls_or_default(urls: Iterable[str]) -> list[str]:
	"""The configured URLs without blanks, or the defaults when none is configured."""
	cleaned = [url.strip() for url in urls if url and url.strip()]
	return cleaned or list(DEFAULT_TSA_URLS)


class FallbackTimeStamper(TimeStamper):
	"""Asks each TSA in turn and uses the first granted response."""

	def __init__(
		self,
		urls: list[str],
		timeout: int = TIMEOUT_SECONDS,
		factory: TimeStamperFactory = http_timestamper,
	) -> None:
		if not urls:
			raise ValueError("At least one TSA URL is required")
		super().__init__()  # type: ignore[no-untyped-call]
		self.urls = list(urls)
		self.timeout = timeout
		self.factory = factory

	async def async_request_tsa_response(self, req: tsp.TimeStampReq) -> tsp.TimeStampResp:
		failures = []
		for url in self.urls:
			try:
				response = await self.factory(url, self.timeout).async_request_tsa_response(req)
				status = response["status"]["status"].native
			except (TimestampRequestError, OSError, ValueError) as error:
				failures.append(f"{url}: {error}")
				continue
			if status in GRANTED:
				return response
			failures.append(f"{url}: status {status}")
		raise TimestampRequestError("No TSA granted a timestamp. " + "; ".join(failures))


def probe(url: str, timeout: int = 5, factory: TimeStamperFactory = http_timestamper) -> str | None:
	"""Ask one TSA for a timestamp of a dummy digest. None when it grants one, else why not.
	Used by the health panel; it never raises."""
	request = tsp.TimeStampReq(
		{
			"version": "v1",
			"message_imprint": tsp.MessageImprint(
				{
					"hash_algorithm": algos.DigestAlgorithm({"algorithm": "sha256"}),
					"hashed_message": hashlib.sha256(b"frappe-sign-health-check").digest(),
				}
			),
			"nonce": secrets.randbits(63),
			"cert_req": True,
		}
	)
	try:
		response = asyncio.run(factory(url, timeout).async_request_tsa_response(request))
		status = response["status"]["status"].native
	except (TimestampRequestError, OSError, ValueError) as error:
		return f"{url}: {error}"
	return None if status in GRANTED else f"{url}: status {status}"
