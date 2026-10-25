"""pdf/source.py: render a Print Format with frappe.get_print and the Print Format's own generator."""

import unittest
from unittest.mock import patch

import frappe

from frappe_sign.pdf.pages import open_pdf
from frappe_sign.pdf.source import print_generator, render, render_print
from frappe_sign.pdf.types import PdfRenderFailed
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import fixture_pdf
from frappe_sign.tests.printing import generator_available, make_print_format

HTML = "<h1>Frappe Sign source test</h1><p>{{ doc.description }}</p>"


class TestRenderPrint(SignTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Render me please"}).insert()

	def test_uses_the_print_format_generator(self):
		for generator in ("chrome", "wkhtmltopdf"):
			with self.subTest(generator=generator):
				print_format = make_print_format("ToDo", HTML, generator)
				with fake_generators() as calls:
					rendered = render("ToDo", self.todo.name, print_format.name, None)
				self.assertEqual(calls, [generator])
				self.assertEqual(rendered.generator, generator)
				self.assertEqual(rendered.pdf, fixture_pdf())

	def test_stale_form_dict_generator_is_ignored_and_restored(self):
		print_format = make_print_format("ToDo", HTML, "chrome")
		frappe.local.form_dict = frappe._dict(pdf_generator="wkhtmltopdf", keep="me")
		with fake_generators() as calls:
			render_print("ToDo", self.todo.name, print_format.name, None)
		self.assertEqual(calls, ["chrome"])
		self.assertEqual(frappe.local.form_dict, {"pdf_generator": "wkhtmltopdf", "keep": "me"})

	def test_form_dict_gets_no_generator_left_behind(self):
		print_format = make_print_format("ToDo", HTML, "chrome")
		frappe.local.form_dict = frappe._dict()
		with fake_generators():
			render_print("ToDo", self.todo.name, print_format.name, None)
		self.assertNotIn("pdf_generator", frappe.local.form_dict)

	def test_print_generator_defaults_to_wkhtmltopdf(self):
		self.assertEqual(print_generator(None), "wkhtmltopdf")
		self.assertEqual(print_generator("Standard"), "wkhtmltopdf")
		self.assertEqual(print_generator(make_print_format("ToDo", HTML, "chrome").name), "chrome")

	def test_generator_errors_become_pdf_render_failed(self):
		print_format = make_print_format("ToDo", HTML, "wkhtmltopdf")
		with patch("frappe.utils.pdf.get_pdf", side_effect=OSError("wkhtmltopdf not found")):
			with self.assertRaises(PdfRenderFailed) as raised:
				render_print("ToDo", self.todo.name, print_format.name, None)
		self.assertIn("wkhtmltopdf not found", str(raised.exception))

	def test_permission_errors_are_not_hidden(self):
		print_format = make_print_format("ToDo", HTML, "chrome")
		with patch("frappe.get_print", side_effect=frappe.PermissionError("no print")):
			with self.assertRaises(frappe.PermissionError):
				render_print("ToDo", self.todo.name, print_format.name, None)

	def test_renders_with_each_installed_generator(self):
		for generator in ("chrome", "wkhtmltopdf"):
			with self.subTest(generator=generator):
				if not generator_available(generator):
					self.skipTest(f"{generator} is not installed")
				print_format = make_print_format("ToDo", HTML, generator)
				pdf = render_print("ToDo", self.todo.name, print_format.name, None)
				text = open_pdf(pdf).pages[0].extract_text()
				self.assertIn("Render me please", text)


class fake_generators:
	"""Replace both PDF generators with stubs that record which one get_print called."""

	def __enter__(self):
		self.calls: list[str] = []
		self.patches = [
			patch("frappe.utils.pdf.get_pdf", side_effect=self.wkhtmltopdf),
			patch("frappe.utils.pdf.get_chrome_pdf", side_effect=self.chrome),
		]
		for item in self.patches:
			item.start()
		return self.calls

	def __exit__(self, *exc):
		for item in self.patches:
			item.stop()

	def wkhtmltopdf(self, html, options=None, output=None):
		self.calls.append("wkhtmltopdf")
		return fixture_pdf()

	def chrome(self, print_format, html, options, output, pdf_generator=None):
		if pdf_generator != "chrome":
			return None
		self.calls.append("chrome")
		return fixture_pdf()


if __name__ == "__main__":
	unittest.main()
