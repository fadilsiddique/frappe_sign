"""crypto/ (P1.4): PKCS#12 inspection, the Signer protocol and the TSA fallback."""

import asyncio
from datetime import datetime
from pathlib import Path

from asn1crypto import tsp
from frappe.tests import UnitTestCase
from pyhanko.keys import load_cert_from_pemder, load_private_key_from_pemder
from pyhanko.sign.timestamps import TimestampRequestError
from pyhanko.sign.timestamps.dummy_client import DummyTimeStamper

from frappe_sign.crypto.pkcs12 import Pkcs12Error, inspect, require_usable
from frappe_sign.crypto.signer import Pkcs12Signer, Signer, SignerError
from frappe_sign.crypto.tsa import DEFAULT_TSA_URLS, FallbackTimeStamper, tsa_urls_or_default

CERTS = Path(__file__).resolve().parents[1] / "fixtures" / "certs"
PASSWORD = b"fixture-seal"


def p12(name: str) -> bytes:
	return (CERTS / name).read_bytes()


def dummy_tsa() -> DummyTimeStamper:
	return DummyTimeStamper(
		tsa_cert=load_cert_from_pemder(str(CERTS / "tsa.pem")),
		tsa_key=load_private_key_from_pemder(str(CERTS / "tsa.key.pem"), None),
	)


class FailingTimeStamper(DummyTimeStamper):
	def __init__(self, url: str):
		self.url = url

	async def async_request_tsa_response(self, req: tsp.TimeStampReq) -> tsp.TimeStampResp:
		raise TimestampRequestError(f"{self.url} is down")


class TestPkcs12(UnitTestCase):
	def test_inspect_reads_the_sealing_certificate(self):
		info = inspect(p12("sealing.p12"), PASSWORD)
		self.assertIn("Frappe Sign Test Seal", info.subject)
		self.assertIn("Frappe Sign Test Root CA", info.issuer)
		self.assertEqual(info.valid_from, datetime(2026, 1, 1))
		self.assertEqual(info.valid_to, datetime(2041, 1, 1))
		self.assertRegex(info.fingerprint_sha256, r"^[0-9a-f]{64}$")
		self.assertTrue(info.has_key)
		require_usable(info, now=datetime(2026, 6, 1))

	def test_wrong_password(self):
		with self.assertRaises(Pkcs12Error) as caught:
			inspect(p12("sealing.p12"), b"wrong")
		self.assertEqual(caught.exception.reason, "wrong_password")

	def test_not_a_pkcs12_file(self):
		with self.assertRaises(Pkcs12Error) as caught:
			inspect(b"garbage", PASSWORD)
		self.assertEqual(caught.exception.reason, "wrong_password")

	def test_expired_and_key_less_files_are_not_usable(self):
		expired = inspect(p12("sealing_expired.p12"), PASSWORD)
		with self.assertRaises(Pkcs12Error) as caught:
			require_usable(expired, now=datetime(2026, 6, 1))
		self.assertEqual(caught.exception.reason, "expired")

		key_less = inspect(p12("sealing_no_key.p12"), PASSWORD)
		self.assertFalse(key_less.has_key)
		self.assertIn("Frappe Sign Test Seal", key_less.subject)
		with self.assertRaises(Pkcs12Error) as caught:
			require_usable(key_less, now=datetime(2026, 6, 1))
		self.assertEqual(caught.exception.reason, "no_key")

	def test_not_yet_valid(self):
		with self.assertRaises(Pkcs12Error) as caught:
			require_usable(inspect(p12("sealing.p12"), PASSWORD), now=datetime(2025, 6, 1))
		self.assertEqual(caught.exception.reason, "not_yet_valid")


class TestPkcs12Signer(UnitTestCase):
	def test_satisfies_the_signer_protocol(self):
		signer = Pkcs12Signer(p12("sealing.p12"), PASSWORD)
		self.assertIsInstance(signer, Signer)
		pyhanko_signer = signer.pyhanko_signer()
		self.assertIn("Frappe Sign Test Seal", pyhanko_signer.signing_cert.subject.human_friendly)
		self.assertIs(signer.pyhanko_signer(), pyhanko_signer)

	def test_rejects_unusable_files(self):
		for name, password in (
			("sealing.p12", b"wrong"),
			("sealing_expired.p12", PASSWORD),
			("sealing_no_key.p12", PASSWORD),
		):
			with self.subTest(name=name), self.assertRaises(SignerError):
				Pkcs12Signer(p12(name), password).pyhanko_signer()

	def test_never_shows_the_password(self):
		signer = Pkcs12Signer(p12("sealing.p12"), PASSWORD)
		self.assertNotIn("fixture-seal", repr(signer))


class TestTimestamps(UnitTestCase):
	def test_settings_urls_win_and_defaults_fill_in(self):
		self.assertEqual(
			tsa_urls_or_default(["http://a.test", " ", "http://b.test"]), ["http://a.test", "http://b.test"]
		)
		self.assertEqual(tsa_urls_or_default([]), list(DEFAULT_TSA_URLS))

	def test_falls_back_to_the_next_url(self):
		tried = []

		def factory(url: str, timeout: int):
			tried.append((url, timeout))
			return FailingTimeStamper(url) if "down" in url else dummy_tsa()

		stamper = FallbackTimeStamper(["http://down.test", "http://up.test"], factory=factory)
		token = asyncio.run(stamper.async_timestamp(b"\x00" * 32, "sha256"))
		self.assertEqual(token["content_type"].native, "signed_data")
		self.assertEqual(tried, [("http://down.test", 10), ("http://up.test", 10)])

	def test_all_urls_failing_raises(self):
		stamper = FallbackTimeStamper(
			["http://a.test", "http://b.test"], factory=lambda url, timeout: FailingTimeStamper(url)
		)
		with self.assertRaises(TimestampRequestError) as caught:
			asyncio.run(stamper.async_timestamp(b"\x00" * 32, "sha256"))
		self.assertIn("http://a.test", str(caught.exception))
		self.assertIn("http://b.test", str(caught.exception))

	def test_needs_at_least_one_url(self):
		with self.assertRaises(ValueError):
			FallbackTimeStamper([])
