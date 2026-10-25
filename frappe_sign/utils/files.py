"""Private Files that the app creates (golden rule 8, D11)."""

import frappe


def new_private_file(content: bytes, file_name: str, doctype: str, name: str):
	"""A File document, not yet inserted. Callers insert it, so the permission check stays visible."""
	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": file_name,
			"content": content,
			"attached_to_doctype": doctype,
			"attached_to_name": name,
			"is_private": 1,
		}
	)


def read_file(name: str) -> bytes:
	"""Raw bytes of a File by its name (Link File fields store the name).

	File.get_content() returns str when the bytes happen to decode as UTF-8, so read the disk file.
	"""
	# get_full_path() resolves inside the site's files folder and refuses paths outside it.
	path = frappe.get_doc("File", name).get_full_path()
	with open(path, "rb") as handle:  # nosemgrep: frappe-security-file-traversal
		return handle.read()


def read_file_url(file_url: str) -> bytes:
	name = frappe.db.get_value("File", {"file_url": file_url}, "name")
	if not name:
		raise frappe.DoesNotExistError(f"File {file_url} not found")
	return read_file(name)
