"""SHA-256 helpers for tokens, secrets, OTPs and files."""

import base64
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
	"""A random 32-byte secret, such as a guest session secret. Only its SHA-256 is stored."""
	return secrets.token_urlsafe(32)


def derive_token(key: str, recipient_row: str, version: int) -> str:
	"""A recipient link token (D10): HMAC-SHA256 of the row and version under the site's key.

	The same row and version give the same link, so reminders can resend it; a new version (resend)
	gives a new link and the old one stops working. Only sha256(token) is stored, and the key lives in
	site_config, so the database alone does not reveal live links.
	"""
	message = f"frappe_sign:link:{recipient_row}:{version}".encode()
	digest = hmac.new(key.encode(), message, hashlib.sha256).digest()
	return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def new_otp() -> str:
	return f"{secrets.randbelow(10**6):06d}"


def same_digest(value: str, digest: str | None) -> bool:
	"""Constant-time check that sha256(value) equals a stored digest."""
	return bool(digest) and hmac.compare_digest(sha256_hex(value), digest)
