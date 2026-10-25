"""Delete what tests had to commit (threads, jobs, browsers), so the test site stays clean."""

import os

import frappe
from frappe.utils import get_files_path

TEST_EMAIL_ACCOUNT = "sign-test@example.com"


def purge_envelope(envelope: str | None) -> list[str]:
	"""Delete an envelope with its rows, events, sessions, captures and emails. Returns templates."""
	if not envelope:
		return []
	version = frappe.db.get_value("Sign Envelope", envelope, "template_version")
	templates = [frappe.db.get_value("Sign Template Version", version, "template")] if version else []
	for doctype in ("Sign Event", "Sign Session", "Sign Capture"):
		frappe.db.delete(doctype, {"envelope": envelope})
	for doctype in ("Sign Envelope Recipient", "Sign Envelope Field"):
		frappe.db.delete(doctype, {"parent": envelope})
	frappe.db.delete("Sign Envelope", {"name": envelope})
	queued = frappe.get_all("Email Queue", filters={"reference_name": envelope}, pluck="name")
	if queued:
		frappe.db.delete("Email Queue Recipient", {"parent": ["in", queued]})
		frappe.db.delete("Email Queue", {"name": ["in", queued]})
	frappe.db.delete("Notification Log", {"document_name": envelope})
	frappe.db.delete("Error Log", {"reference_name": envelope})
	return [template for template in templates if template]


def purge_template(template: str) -> None:
	frappe.db.delete("Sign Template Version", {"template": template})
	for doctype in ("Sign Template Role", "Sign Template Field"):
		frappe.db.delete(doctype, {"parent": template})
	frappe.db.delete("Sign Template", {"name": template})


def purge_profile(company: str) -> None:
	certificate = frappe.db.get_value("Sign Profile", company, "sealing_certificate")
	frappe.db.delete("Sign Profile", {"name": company})
	if certificate:
		frappe.db.delete("Sign Certificate", {"name": certificate})
		frappe.db.delete("__Auth", {"doctype": "Sign Certificate", "name": certificate})


def purge_since(started) -> None:
	"""Files (rows and disk) and Version rows created since `started`, and the test Email Account."""
	frappe.db.delete("Version", {"creation": [">=", started], "ref_doctype": ["like", "Sign %"]})
	for file in frappe.get_all(
		"File", filters={"creation": [">=", started]}, fields=["name", "file_url", "is_private"]
	):
		if file.file_url:
			path = get_files_path(file.file_url.rsplit("/", 1)[-1], is_private=file.is_private)
			if os.path.exists(path):
				os.remove(path)
		frappe.db.delete("File", {"name": file.name})
	frappe.db.delete("Email Account", {"email_id": TEST_EMAIL_ACCOUNT})
