"""Sign Certificate from Desk: "Create test certificate" makes a self-signed one (ADMIN_GUIDE step 2).

It gives a trial or pilot site a working seal in one step: a new key and certificate, a private
File, the Sign Certificate, and the company's Sign Profile pointing at it. Adobe Reader shows a
self-signed seal as "identity unknown"; production sites upload a CA-issued or AATL certificate.
"""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_datetime, now_datetime

from frappe_sign.crypto.selfsigned import MAX_YEARS, make_self_signed
from frappe_sign.exceptions import CertificateError, throw
from frappe_sign.services import notify
from frappe_sign.utils.files import new_private_file


def create_test_certificate(
	company: str | None = None, common_name: str | None = None, years: int = 3, replace: bool = False
) -> dict[str, str | None]:
	"""Make and store a self-signed certificate, and use it in the company's Sign Profile.

	The profile is created when the company has none, and linked when it has no certificate yet.
	An existing certificate on a profile is replaced only with `replace` (Settings, for an expired seal).
	"""
	frappe.has_permission("Sign Certificate", "create", throw=True)
	company = (company or "").strip() or None
	common_name = (common_name or company or "").strip()
	if not common_name:
		throw(CertificateError, _("Enter the name to show on the certificate."))
	if not 1 <= years <= MAX_YEARS:
		throw(CertificateError, _("Validity must be 1 to {0} years.").format(MAX_YEARS))

	material = make_self_signed(common_name, organization=company, years=years)
	file = new_private_file(material.p12, f"{frappe.scrub(common_name)}-self-signed.p12", None, None)
	file.insert()
	certificate = frappe.get_doc(
		{
			"doctype": "Sign Certificate",
			"title": _("{0} (self-signed)").format(common_name),
			"company": company,
			"kind": "Self-signed",
			"storage": "PKCS#12 File",
			"p12_file": file.file_url,
			"p12_password": material.password,
		}
	).insert()
	file.db_set({"attached_to_doctype": "Sign Certificate", "attached_to_name": certificate.name})
	profile, profile_action = use_in_profile(company, certificate.name, replace)
	return {"certificate": certificate.name, "profile": profile, "profile_action": profile_action}


def use_in_profile(
	company: str | None, certificate: str, replace: bool = False
) -> tuple[str | None, str | None]:
	"""(profile, "created" | "linked") or (profile or None, None) when nothing changed."""
	name = company if company else notify.single_profile()
	if name and frappe.db.exists("Sign Profile", name):
		profile = frappe.get_doc("Sign Profile", name)
		if (profile.sealing_certificate and not replace) or not profile.has_permission("write"):
			return profile.name, None
		profile.sealing_certificate = certificate
		profile.save()
		return profile.name, "linked"
	if not company or not frappe.has_permission("Sign Profile", "create"):
		return None, None
	profile = frappe.get_doc(
		{"doctype": "Sign Profile", "company": company, "sealing_certificate": certificate}
	).insert()
	return profile.name, "created"


def upload_certificate(
	company: str, file_name: str, content: bytes, password: str, kind: str = "CA-issued"
) -> dict[str, str | None]:
	"""Store an uploaded PKCS#12 file as a Sign Certificate and make it the company's seal.

	The certificate's own validation opens the file with the password. Unlike the test seal, this
	replaces the profile's current certificate: the user chose the new one on purpose.
	"""
	frappe.has_permission("Sign Certificate", "create", throw=True)
	if kind not in ("CA-issued", "AATL"):
		throw(CertificateError, _("Choose CA-issued or AATL."))
	if not content:
		throw(CertificateError, _("Choose the PKCS#12 (.p12) file."))
	file = new_private_file(content, file_name, None, None)
	file.insert()
	certificate = frappe.get_doc(
		{
			"doctype": "Sign Certificate",
			"title": _("{0} ({1})").format(company, kind),
			"company": company,
			"kind": kind,
			"storage": "PKCS#12 File",
			"p12_file": file.file_url,
			"p12_password": password,
		}
	).insert()
	file.db_set({"attached_to_doctype": "Sign Certificate", "attached_to_name": certificate.name})
	profile, profile_action = use_in_profile(company, certificate.name, replace=True)
	return {"certificate": certificate.name, "profile": profile, "profile_action": profile_action}


def seal_details(certificate: str | None) -> dict[str, object]:
	"""What the staff app shows of a seal: kind, end of validity and whether it has run out.
	Read straight from the database: a Sign Manager cannot open a Sign Certificate (D11)."""
	details = certificate and frappe.db.get_value(
		"Sign Certificate", certificate, ["kind", "valid_to"], as_dict=True
	)
	if not details:
		return {"kind": None, "valid_to": None, "expired": False}
	valid_to = details.valid_to
	return {
		"kind": details.kind,
		"valid_to": str(valid_to.date()) if valid_to else None,
		"expired": bool(valid_to) and get_datetime(valid_to) <= now_datetime(),
	}
