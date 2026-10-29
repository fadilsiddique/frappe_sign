"""crypto/remote.py (P3.6): RemoteSigner over PKCS#11 (SoftHSM) and CSC (a fake service), offline."""

import asyncio
import base64
import threading
from datetime import UTC, datetime, timedelta

from aiohttp import web
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, utils
from cryptography.hazmat.primitives.serialization import pkcs12
from frappe.tests import UnitTestCase

from frappe_sign.crypto.remote import RemoteSigner
from frappe_sign.crypto.signer import Signer, SignerError
from frappe_sign.pdf.seal import seal_pdf
from frappe_sign.pdf.types import SealError
from frappe_sign.tests import pki, softhsm
from frappe_sign.utils.remote_config import RemoteConfigError, parse_config

PDF = (pki.CERTS.parent / "pdfs" / "a4_simple.pdf").read_bytes()


def seal(signer: Signer) -> bytes:
	return seal_pdf(
		PDF,
		signer=signer,
		tsa_urls=["http://tsa.invalid"],
		reason="Signed with Frappe Sign",
		location="Dubai",
		contact="sign@example.com",
		timestamper=pki.timestamper(),
		validation_context=pki.sealing_validation_context(),
	)


def assert_valid(test: UnitTestCase, sealed: bytes) -> None:
	status = pki.validate_lt(sealed)
	test.assertTrue(status.bottom_line, status.pretty_print_details())
	test.assertTrue(status.intact and status.valid and status.trusted)


class TestConfig(UnitTestCase):
	def test_pkcs11_needs_a_module_a_token_and_a_key(self):
		good = {"type": "pkcs11", "module_path": "/lib/x.so", "token_label": "t", "key_label": "k"}
		self.assertEqual(parse_config(good)["key_label"], "k")
		for missing in ("module_path", "token_label", "key_label"):
			with self.assertRaises(RemoteConfigError, msg=missing):
				parse_config({k: v for k, v in good.items() if k != missing})

	def test_pkcs11_module_must_be_an_absolute_library_path(self):
		base = {"type": "pkcs11", "token_label": "t", "key_label": "k"}
		for path in ("libx.so", "/lib/../x.so", "/etc/passwd", "/lib/x.so\0"):
			with self.assertRaises(RemoteConfigError, msg=path):
				parse_config(base | {"module_path": path})

	def test_csc_needs_https_except_for_loopback(self):
		base = {"type": "csc", "credential_id": "c"}
		parse_config(base | {"service_url": "https://csc.example.com"})
		parse_config(base | {"service_url": "http://127.0.0.1:9000"})
		for url in ("http://csc.example.com", "ftp://x", "csc.example.com", ""):
			with self.assertRaises(RemoteConfigError, msg=url):
				parse_config(base | {"service_url": url})

	def test_unknown_type_and_bad_json(self):
		for raw in ("{not json", "[]", '{"type": "other"}', None, ""):
			with self.assertRaises(RemoteConfigError, msg=raw):
				parse_config(raw)

	def test_unknown_keys_are_refused(self):
		with self.assertRaises(RemoteConfigError):
			parse_config(
				{"type": "csc", "credential_id": "c", "service_url": "https://x.example.com", "pin": "1234"}
			)


class TestPkcs11(UnitTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.token = softhsm.require()

	def config(self, **overrides) -> dict:
		return {
			"type": "pkcs11",
			"module_path": self.token.module_path,
			"token_label": self.token.token_label,
			"key_label": self.token.key_label,
			"cert_label": self.token.key_label,
		} | overrides

	def signer(self, pin: str | None = None, **overrides) -> RemoteSigner:
		return RemoteSigner(self.config(**overrides), pin=self.token.pin if pin is None else pin)

	def test_seals_a_pdf_that_validates_as_pades_b_lt(self):
		assert_valid(self, seal(self.signer()))

	def test_chain_has_the_signing_certificate(self):
		subjects = [cert.subject.human_friendly for cert in self.signer().chain()]
		self.assertTrue(any("Frappe Sign Test Seal" in subject for subject in subjects))

	def test_the_signer_can_seal_twice(self):
		signer = self.signer()
		assert_valid(self, seal(signer))
		assert_valid(self, seal(signer))

	def test_a_wrong_pin_is_a_seal_error_and_never_shows_the_pin(self):
		with self.assertRaises(SealError) as caught:
			seal(self.signer(pin="0000"))
		self.assertNotIn("0000", str(caught.exception))

	def test_an_unknown_key_or_token_is_a_seal_error(self):
		for overrides in ({"key_label": "nope", "cert_label": "nope"}, {"token_label": "NoSuchToken"}):
			with self.subTest(overrides), self.assertRaises(SealError):
				seal(self.signer(**overrides))

	def test_a_missing_module_is_a_seal_error(self):
		with self.assertRaises(SealError):
			seal(self.signer(module_path="/nonexistent/libsofthsm2.so"))

	def test_repr_hides_the_pin(self):
		self.assertNotIn(self.token.pin, repr(self.signer()))


class FakeCsc:
	"""A CSC v1 service in a thread: credentials/info, credentials/authorize and signatures/signHash,
	signing with the test sealing key."""

	def __init__(self, *, pin: str = "9999", token: str = "oauth-token", valid: bool = True):
		key, cert, chain = pkcs12.load_key_and_certificates(
			(pki.CERTS / "sealing.p12").read_bytes(), pki.P12_PASSWORD
		)
		self.key, self.pin, self.token = key, pin, token
		self.certs = [cert, *(chain or [])] if valid else []
		self.requests: list[str] = []
		self.loop = asyncio.new_event_loop()
		self.ready = threading.Event()
		self.url = ""
		threading.Thread(target=self.serve, daemon=True).start()
		self.ready.wait(10)

	def serve(self) -> None:
		asyncio.set_event_loop(self.loop)
		app = web.Application()
		app.router.add_post("/csc/v1/credentials/info", self.info)
		app.router.add_post("/csc/v1/credentials/authorize", self.authorize)
		app.router.add_post("/csc/v1/signatures/signHash", self.sign_hash)
		self.runner = web.AppRunner(app)
		self.loop.run_until_complete(self.runner.setup())
		site = web.TCPSite(self.runner, "127.0.0.1", 0)
		self.loop.run_until_complete(site.start())
		port = site._server.sockets[0].getsockname()[1]  # type: ignore[union-attr]
		self.url = f"http://127.0.0.1:{port}"
		self.ready.set()
		self.loop.run_forever()

	def stop(self) -> None:
		self.loop.call_soon_threadsafe(self.loop.stop)

	def check(self, request: web.Request) -> None:
		self.requests.append(request.path)
		if request.headers.get("Authorization") != f"Bearer {self.token}":
			raise web.HTTPUnauthorized()

	async def info(self, request: web.Request) -> web.Response:
		self.check(request)
		certificates = [
			base64.b64encode(cert.public_bytes(serialization.Encoding.DER)).decode() for cert in self.certs
		]
		return web.json_response(
			{
				"cert": {"certificates": certificates},
				"key": {"algo": ["1.2.840.113549.1.1.11"]},
				"multisign": 1,
				"SCAL": 1,
			}
		)

	async def authorize(self, request: web.Request) -> web.Response:
		self.check(request)
		body = await request.json()
		if body.get("PIN") != self.pin:
			raise web.HTTPForbidden()
		return web.json_response({"SAD": "sad-1", "expiresIn": 300})

	async def sign_hash(self, request: web.Request) -> web.Response:
		self.check(request)
		body = await request.json()
		if body.get("SAD") != "sad-1":
			raise web.HTTPForbidden()
		signatures = [
			base64.b64encode(
				self.key.sign(base64.b64decode(digest), padding.PKCS1v15(), utils.Prehashed(hashes.SHA256()))
			).decode()
			for digest in body["hash"]
		]
		return web.json_response({"signatures": signatures})


class TestCsc(UnitTestCase):
	def start(self, **options) -> FakeCsc:
		service = FakeCsc(**options)
		self.addCleanup(service.stop)
		return service

	def signer(self, service: FakeCsc, **overrides) -> RemoteSigner:
		config = {"type": "csc", "service_url": service.url, "credential_id": "cred-1"}
		return RemoteSigner(
			config, pin=overrides.get("pin", service.pin), token=overrides.get("token", service.token)
		)

	def test_seals_a_pdf_that_validates_as_pades_b_lt(self):
		service = self.start()
		assert_valid(self, seal(self.signer(service)))
		self.assertIn("/csc/v1/signatures/signHash", service.requests)

	def test_chain_comes_from_credentials_info(self):
		service = self.start()
		subjects = [cert.subject.human_friendly for cert in self.signer(service).chain()]
		self.assertTrue(any("Frappe Sign Test Seal" in subject for subject in subjects))

	def test_a_wrong_pin_or_token_is_a_seal_error(self):
		service = self.start()
		for overrides in ({"pin": "0000"}, {"token": "wrong"}):
			with self.subTest(overrides), self.assertRaises(SealError):
				seal(self.signer(service, **overrides))

	def test_a_credential_without_certificates_is_a_seal_error(self):
		service = self.start(valid=False)
		with self.assertRaises(SealError):
			seal(self.signer(service))

	def test_an_unreachable_service_is_a_seal_error(self):
		service = self.start()
		signer = self.signer(service)
		service.stop()
		signer._config["service_url"] = "http://127.0.0.1:9"
		with self.assertRaises(SealError):
			seal(signer)

	def test_the_secrets_are_not_in_the_repr(self):
		service = self.start()
		text = repr(self.signer(service))
		self.assertNotIn(service.pin, text)
		self.assertNotIn(service.token, text)


class TestValidityWindow(UnitTestCase):
	def test_an_expired_certificate_is_refused(self):
		from frappe_sign.crypto.remote import require_valid_now

		cert = pki_cert("sealing_expired.p12")
		with self.assertRaises(SignerError):
			require_valid_now(cert, datetime.now(UTC))
		require_valid_now(pki_cert("sealing.p12"), datetime.now(UTC) + timedelta(days=1))


def pki_cert(name: str):
	from asn1crypto import x509

	_key, cert, _chain = pkcs12.load_key_and_certificates((pki.CERTS / name).read_bytes(), pki.P12_PASSWORD)
	assert cert is not None
	return x509.Certificate.load(cert.public_bytes(serialization.Encoding.DER))
