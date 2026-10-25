"""sign_field() anchors in a Quotation Print Format, rendered by wkhtmltopdf and chrome (P2.2).

Each generator's test skips when that generator is not installed; CI installs both.
"""

import unittest

from frappe_sign.pdf.anchors import MM, find_anchors
from frappe_sign.pdf.pages import page_metrics
from frappe_sign.pdf.sanitize import sanitize
from frappe_sign.pdf.source import render
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_quotation
from frappe_sign.tests.printing import GENERATORS, generator_available, make_print_format

QUOTATION_HTML = """
<div style="font-family: sans-serif; font-size: 10pt;">
  <h2>Quotation {{ doc.name }}</h2>
  <p>{{ doc.customer_name }}</p>
  <table style="width: 100%; border-collapse: collapse;">
    <thead><tr><th>#</th><th>Item</th><th>Qty</th><th>Rate</th><th>Amount</th></tr></thead>
    <tbody>
    {% for row in doc.items %}
      <tr style="height: 8mm;">
        <td>{{ row.idx }}</td><td>{{ row.item_name }}</td><td>{{ row.qty }}</td>
        <td>{{ row.rate }}</td><td>{{ row.amount }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
  <p>Total: {{ doc.grand_total }}</p>
  <table style="width: 100%; margin-top: 10mm; page-break-inside: avoid;">
    <tr>
      <td>Customer<br>{{ sign_field("signature", role="Customer", width=60, height=20, border=True) }}
        <br>Date: {{ sign_field("date_signed", role="Customer") }}</td>
      <td>For {{ doc.company }}<br>{{ sign_field("signature", role="Company", width=60, height=20, border=True) }}</td>
    </tr>
  </table>
</div>
"""
TAGS = {"[[fs:Customer:signature:1]]", "[[fs:Customer:date_signed:1]]", "[[fs:Company:signature:1]]"}
# Size tolerance: the generators round to device pixels.
SIZE_TOLERANCE = 0.03


class TestQuotationAnchors(ERPNextTestCase):
	needs_email_account = False

	def check_generator(self, generator: str, items: int) -> None:
		if not generator_available(generator):
			self.skipTest(f"{generator} is not installed")
		quotation = make_quotation(items=items)
		print_format = make_print_format("Quotation", QUOTATION_HTML, generator)
		rendered = render("Quotation", quotation.name, print_format.name, None)
		self.assertEqual(rendered.generator, generator)
		frozen = sanitize(rendered.pdf, max_bytes=50 * 1024 * 1024, max_pages=200).data
		anchors = {anchor.tag: anchor for anchor in find_anchors(frozen, rendered.declared)}
		self.assertEqual(set(anchors), TAGS)

		pages = page_metrics(frozen)
		last = len(pages)
		if items >= 40:
			self.assertGreater(last, 1)
		self.assertEqual({anchor.page for anchor in anchors.values()}, {last})

		metric = pages[-1]
		customer, company = anchors["[[fs:Customer:signature:1]]"], anchors["[[fs:Company:signature:1]]"]
		date = anchors["[[fs:Customer:date_signed:1]]"]
		for anchor in (customer, company):
			self.assertAlmostEqual(anchor.rect.w * metric.display_width / MM, 60, delta=60 * SIZE_TOLERANCE)
			self.assertAlmostEqual(anchor.rect.h * metric.display_height / MM, 20, delta=20 * SIZE_TOLERANCE)
		self.assertLess(customer.rect.x + customer.rect.w, company.rect.x)
		# The date line starts where the signature box ends (they touch; allow one point).
		self.assertGreater(date.rect.y, customer.rect.y + customer.rect.h - 1 / metric.display_height)

	def test_three_items(self):
		for generator in GENERATORS:
			with self.subTest(generator=generator):
				self.check_generator(generator, 3)

	def test_forty_items(self):
		for generator in GENERATORS:
			with self.subTest(generator=generator):
				self.check_generator(generator, 40)


if __name__ == "__main__":
	unittest.main()
