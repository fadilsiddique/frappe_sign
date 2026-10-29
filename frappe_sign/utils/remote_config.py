"""Validate the JSON of a remote Sign Certificate (PKCS#11 token or CSC service), P3.6.

Pure: no Frappe, no pyHanko. Secrets (PIN, access token) never live here; they are Password
fields on the Sign Certificate. Unknown keys are refused so a secret pasted into the JSON is
noticed instead of being stored in plain text.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

PKCS11, CSC = "pkcs11", "csc"
LIBRARY_SUFFIXES = (".so", ".dylib", ".dll")
LOOPBACK = ("127.0.0.1", "localhost", "::1")
KEYS = {
	PKCS11: {"type", "module_path", "token_label", "slot_no", "key_label", "cert_label"},
	CSC: {"type", "service_url", "credential_id", "api_version"},
}


class RemoteConfigError(ValueError):
	"""The remote signing JSON is wrong; the message says what to fix."""


def parse_config(raw: str | dict[str, Any] | None) -> dict[str, Any]:
	config = load(raw)
	kind = config.get("type")
	if kind not in KEYS:
		raise RemoteConfigError('"type" must be "pkcs11" or "csc".')
	unknown = sorted(set(config) - KEYS[kind])
	if unknown:
		raise RemoteConfigError(
			f"Unknown keys: {', '.join(unknown)}. PINs and tokens go in their own fields, not here."
		)
	check_pkcs11(config) if kind == PKCS11 else check_csc(config)
	return config


def load(raw: str | dict[str, Any] | None) -> dict[str, Any]:
	if isinstance(raw, str):
		try:
			raw = json.loads(raw) if raw.strip() else None
		except json.JSONDecodeError as error:
			raise RemoteConfigError(f"The JSON is not valid: {error.msg}.") from error
	if not isinstance(raw, dict):
		raise RemoteConfigError("Enter the remote signing settings as a JSON object.")
	return dict(raw)


def check_pkcs11(config: dict[str, Any]) -> None:
	module = text(config, "module_path")
	if (
		not module.startswith("/")
		or "\0" in module
		or ".." in module.split("/")
		or not module.lower().endswith(LIBRARY_SUFFIXES)
	):
		raise RemoteConfigError('"module_path" must be the absolute path of a PKCS#11 library (.so, .dylib).')
	if not config.get("token_label") and config.get("slot_no") is None:
		raise RemoteConfigError('Give the "token_label" (or a "slot_no") of the token.')
	if not (config.get("key_label") or config.get("cert_label")):
		raise RemoteConfigError('Give the "key_label" of the signing key on the token.')
	for key in ("token_label", "key_label", "cert_label"):
		if key in config and not isinstance(config[key], str):
			raise RemoteConfigError(f'"{key}" must be text.')
	if config.get("slot_no") is not None and not isinstance(config["slot_no"], int):
		raise RemoteConfigError('"slot_no" must be a number.')


def check_csc(config: dict[str, Any]) -> None:
	text(config, "credential_id")
	url = urlsplit(text(config, "service_url"))
	secure = url.scheme == "https" or (url.scheme == "http" and url.hostname in LOOPBACK)
	if not secure or not url.hostname or url.username or url.password:
		raise RemoteConfigError('"service_url" must be an https address, such as https://csc.example.com.')
	if not str(config.get("api_version", "v1")).isalnum():
		raise RemoteConfigError('"api_version" must be like v1.')


def text(config: dict[str, Any], key: str) -> str:
	value = config.get(key)
	if not isinstance(value, str) or not value.strip():
		raise RemoteConfigError(f'"{key}" is required.')
	return value.strip()
