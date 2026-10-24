"""SHA-256 helpers for tokens, secrets, OTPs and files."""

import hashlib
import re

SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def sha256_hex(data: bytes | str) -> str:
	if isinstance(data, str):
		data = data.encode()
	return hashlib.sha256(data).hexdigest()


def is_sha256_hex(value: str | None) -> bool:
	"""True for a lowercase 64-character hex digest, the only form secrets are stored in."""
	return bool(value) and SHA256_HEX.fullmatch(value) is not None
