# Copyright (c) 2026, Upscape Technologies and contributors
# For license information, please see license.txt

from datetime import UTC, datetime

import frappe
from frappe import _
from frappe.model.document import Document

from frappe_sign.crypto import pkcs12
from frappe_sign.exceptions import CertificateError
from frappe_sign.utils.files import read_file
from frappe_sign.utils.integrity import require_private_files
from frappe_sign.utils.remote_config import RemoteConfigError, parse_config


class SignCertificate(Document):
	"""A sealing certificate. Only System Manager can read it; Sign Manager can only link it.

	On save the PKCS#12 file is parsed and checked (DESIGN 2.1): it must open with the password,
	hold a private key and be valid now. Subject, issuer, validity and fingerprint are filled in.
	"""

	def before_validate(self):
		require_private_files(self, "p12_file")

	def validate(self):
		if self.storage == "Remote":
			self.check_remote_config()
			return
		self.read_pkcs12()

	def check_remote_config(self):
		try:
			parse_config(self.remote_config)
		except RemoteConfigError as error:
			frappe.throw(str(error), CertificateError)
		if not self.remote_pin:
			frappe.msgprint(_("No PIN is set: only a token that needs none can sign."), indicator="orange")

	def read_pkcs12(self):
		password = self.plain_password()
		if not self.p12_file or not password:
			frappe.throw(_("Attach the PKCS#12 (.p12) file and enter its password."), CertificateError)
		try:
			info = pkcs12.inspect(read_private_file(self.p12_file), password.encode())
			pkcs12.require_usable(info, now=now_utc())
		except pkcs12.Pkcs12Error as error:
			frappe.throw(pkcs12_message(error), CertificateError)
		self.subject = info.subject
		self.issuer = info.issuer
		self.valid_from = info.valid_from
		self.valid_to = info.valid_to
		self.fingerprint_sha256 = info.fingerprint_sha256
		self.public_chain = pkcs12.public_chain_pem(read_private_file(self.p12_file), password.encode())

	def plain_password(self) -> str | None:
		"""The password typed in this save, or the stored one when the field is masked."""
		if self.p12_password and set(self.p12_password) != {"*"}:
			return self.p12_password
		if self.is_new():
			return None
		return self.get_password("p12_password", raise_exception=False)


def pkcs12_message(error: pkcs12.Pkcs12Error) -> str:
	match error.reason:
		case "wrong_password":
			return _("The password is wrong, or the file is not a PKCS#12 (.p12) file.")
		case "no_key":
			return _("The PKCS#12 file has no private key, so it cannot seal documents.")
		case "no_certificate":
			return _("The PKCS#12 file has no certificate.")
		case "expired":
			return _("The certificate has expired: {0}.").format(str(error))
	return _("The certificate is not valid yet: {0}.").format(str(error))


def read_private_file(file_url: str) -> bytes:
	name = frappe.db.get_value("File", {"file_url": file_url, "is_private": 1}, "name")
	if not name:
		frappe.throw(_("File {0} was not found.").format(file_url), CertificateError)
	return read_file(name)


def now_utc():
	return datetime.now(UTC).replace(tzinfo=None)
