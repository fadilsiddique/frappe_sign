"""SHA-256 helpers for tokens, secrets, OTPs and files."""

import hashlib
import hmac
import re
import secrets

SHA256_HEX = re.compile(r"[0-9a-f]{64}")


def sha256_hex(data: bytes | str) -> str:
	if isinstance(data, str):
		data = data.encode()
	return hashlib.sha256(data).hexdigest()


def is_sha256_hex(value: str | None) -> bool:
	"""True for a lowercase 64-character hex digest, the only form secrets are stored in."""
	return bool(value) and SHA256_HEX.fullmatch(value) is not None


def new_token() -> str:
	"""A recipient link token (D10). Only its SHA-256 is stored."""
	return secrets.token_urlsafe(32)


def new_otp() -> str:
	return f"{secrets.randbelow(10**6):06d}"


def same_digest(value: str, digest: str | None) -> bool:
	"""Constant-time check that sha256(value) equals a stored digest."""
	return bool(digest) and hmac.compare_digest(sha256_hex(value), digest)
