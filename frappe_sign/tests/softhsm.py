"""A SoftHSM token holding the test sealing key, for the PKCS#11 tests (P3.6).

SoftHSM reads SOFTHSM2_CONF once, when the library is first loaded in a process, so one token is
made per test process in a temp folder and removed at exit. The tests skip when SoftHSM is not
installed, unless FRAPPE_SIGN_REQUIRE_SOFTHSM is set (CI sets it, so a missing install fails).
"""

from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12

from frappe_sign.tests import pki

MODULES = (
	"/opt/homebrew/lib/softhsm/libsofthsm2.so",
	"/usr/local/lib/softhsm/libsofthsm2.so",
	"/usr/lib/softhsm/libsofthsm2.so",
	"/usr/lib/x86_64-linux-gnu/softhsm/libsofthsm2.so",
	"/usr/lib/aarch64-linux-gnu/softhsm/libsofthsm2.so",
)
TOKEN_LABEL = "FrappeSignTest"
USER_PIN = "1234"
SO_PIN = "5678"
KEY_LABEL = "seal"
KEY_ID = b"\x01"


@dataclass(frozen=True)
class Token:
	module_path: str
	token_label: str
	pin: str
	key_label: str


_token: Token | None = None


def module_path() -> str | None:
	candidates = (os.environ.get("SOFTHSM2_MODULE", ""), *MODULES)
	return next((path for path in candidates if path and Path(path).exists()), None)


def require() -> Token:
	"""The token, or a skipped test when SoftHSM is missing (a failure when CI requires it)."""
	global _token
	if _token is not None:
		return _token
	module = module_path()
	util = shutil.which("softhsm2-util")
	if not module or not util:
		if os.environ.get("FRAPPE_SIGN_REQUIRE_SOFTHSM"):
			raise AssertionError("SoftHSM is required but not installed")
		raise unittest.SkipTest("SoftHSM is not installed")
	_token = build(module, util)
	return _token


def build(module: str, util: str) -> Token:
	folder = Path(tempfile.mkdtemp(prefix="frappe-sign-softhsm-"))
	atexit.register(shutil.rmtree, folder, ignore_errors=True)
	(folder / "tokens").mkdir()
	conf = folder / "softhsm2.conf"
	conf.write_text(
		f"directories.tokendir = {folder / 'tokens'}\nobjectstore.backend = file\nlog.level = ERROR\n"
	)
	os.environ["SOFTHSM2_CONF"] = str(conf)
	run(util, "--init-token", "--free", "--label", TOKEN_LABEL, "--so-pin", SO_PIN, "--pin", USER_PIN)

	key, cert, _chain = pkcs12.load_key_and_certificates(
		(pki.CERTS / "sealing.p12").read_bytes(), pki.P12_PASSWORD
	)
	assert key is not None and cert is not None
	key_file = folder / "key.pem"
	key_file.write_bytes(
		key.private_bytes(
			serialization.Encoding.PEM,
			serialization.PrivateFormat.PKCS8,
			serialization.NoEncryption(),
		)
	)
	run(
		util, "--import", str(key_file), "--token", TOKEN_LABEL, "--label", KEY_LABEL,
		"--id", KEY_ID.hex(), "--pin", USER_PIN,
	)  # fmt: skip
	key_file.unlink()
	store_certificate(module, cert.public_bytes(serialization.Encoding.DER), cert.subject.public_bytes())
	return Token(module, TOKEN_LABEL, USER_PIN, KEY_LABEL)


def store_certificate(module: str, der: bytes, subject: bytes) -> None:
	import pkcs11
	from pkcs11 import Attribute, CertificateType, ObjectClass

	token = pkcs11.lib(module).get_token(token_label=TOKEN_LABEL)
	with token.open(rw=True, user_pin=USER_PIN) as session:
		session.create_object(
			{
				Attribute.CLASS: ObjectClass.CERTIFICATE,
				Attribute.CERTIFICATE_TYPE: CertificateType.X_509,
				Attribute.TOKEN: True,
				Attribute.LABEL: KEY_LABEL,
				Attribute.ID: KEY_ID,
				Attribute.SUBJECT: subject,
				Attribute.VALUE: der,
			}
		)


def run(*command: str) -> None:
	subprocess.run(command, check=True, capture_output=True, text=True)
