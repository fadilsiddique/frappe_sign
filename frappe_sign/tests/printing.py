"""Print Formats and PDF generators for tests of pdf/source.py and pdf/anchors.py.

wkhtmltopdf and Chromium are not on every machine. Tests that render for real skip when the
generator is missing; CI installs both (see .github/workflows/ci.yml).
"""

import os
import shutil
from pathlib import Path

import frappe

GENERATORS = ("wkhtmltopdf", "chrome")
# Where frappe.utils.print_utils.find_or_download_chromium_executable puts Chromium.
CHROMIUM_PATHS = {
	"linux": ("chrome-linux", "headless_shell"),
	"darwin": ("chrome-mac", "headless_shell"),
}


def chromium_available() -> bool:
	configured = frappe.get_common_site_config().get("chromium_path")
	if configured and shutil.which(configured):
		return True
	parts = CHROMIUM_PATHS.get(os.uname().sysname.lower())
	if not parts:
		return False
	return Path(frappe.utils.get_bench_path(), "chromium", *parts).exists()


def wkhtmltopdf_available() -> bool:
	return bool(shutil.which("wkhtmltopdf"))


def generator_available(generator: str) -> bool:
	return chromium_available() if generator == "chrome" else wkhtmltopdf_available()


def make_print_format(doc_type: str, html: str, generator: str = "chrome", **overrides):
	"""A custom Jinja Print Format, not standard, so developer mode does not export it."""
	name = overrides.pop("name", f"Frappe Sign Test {doc_type} {generator}")
	if frappe.db.exists("Print Format", name):
		frappe.delete_doc("Print Format", name, force=True)
	return frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": doc_type,
			"module": "Frappe Sign",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"html": html,
			"pdf_generator": generator,
			**overrides,
		}
	).insert()
