# Test cases for frappe_sign.yml. Run with `semgrep --test .semgrep/rules`.
# This file is never imported; it only has to parse.

import frappe


def permissions(doc):
	# ruleid: frappe-sign-ignore-permissions
	doc.insert(ignore_permissions=True)
	# ruleid: frappe-sign-ignore-permissions
	frappe.get_list("Sign Envelope", ignore_permissions=1)
	# ruleid: frappe-sign-ignore-permissions
	doc.flags.ignore_permissions = True
	# ruleid: frappe-sign-ignore-permissions
	frappe.flags.ignore_permissions = True
	# ok: frappe-sign-ignore-permissions
	doc.insert(ignore_permissions=False)
	# ok: frappe-sign-ignore-permissions
	doc.flags.ignore_permissions = False
	# ok: frappe-sign-ignore-permissions
	doc.insert()


def commits():
	# ruleid: frappe-sign-commit-outside-jobs
	frappe.db.commit()
	# ok: frappe-sign-commit-outside-jobs
	frappe.db.rollback()


def pdf_libraries():
	# ruleid: frappe-sign-agpl-pdf-library
	import fitz

	# ruleid: frappe-sign-agpl-pdf-library
	from pymupdf import Document

	# ok: frappe-sign-agpl-pdf-library
	import pypdf


def files():
	# ruleid: frappe-sign-public-file
	frappe.get_doc({"doctype": "File", "file_name": "a.pdf", "content": b""})
	# ruleid: frappe-sign-public-file
	frappe.get_doc({"doctype": "File", "file_name": "a.pdf", "is_private": 0})
	# ok: frappe-sign-public-file
	frappe.get_doc({"doctype": "File", "file_name": "a.pdf", "is_private": 1})
	# ok: frappe-sign-public-file
	frappe.get_doc({"doctype": "Sign Envelope", "title": "x"})
