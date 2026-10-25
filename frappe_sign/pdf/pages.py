"""Read PDFs with pypdf and measure their pages."""

from __future__ import annotations

import io

from pypdf import PdfReader, PdfWriter
from pypdf._page import PageObject
from pypdf.errors import PyPdfError

from frappe_sign.pdf.types import PageMetric, PdfEncrypted, PdfInvalid


def open_pdf(pdf: bytes) -> PdfReader:
	"""A reader for `pdf`, or PdfInvalid if pypdf cannot parse it. Encrypted PDFs raise PdfEncrypted."""
	try:
		reader = PdfReader(io.BytesIO(pdf), strict=False)
		encrypted = reader.is_encrypted
	except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as error:
		raise PdfInvalid(f"Not a readable PDF: {error}") from error
	if encrypted:
		raise PdfEncrypted("Encrypted PDFs are not accepted")
	return reader


def metric_of(page: PageObject, number: int) -> PageMetric:
	box = page.cropbox
	return PageMetric(
		page=number,
		width=round(float(box.width), 4),
		height=round(float(box.height), 4),
		rotation=int(page.rotation or 0),
		left=round(float(box.left), 4),
		bottom=round(float(box.bottom), 4),
	)


def page_metrics(pdf: bytes) -> list[PageMetric]:
	reader = open_pdf(pdf)
	try:
		return [metric_of(page, number) for number, page in enumerate(reader.pages, start=1)]
	except (PyPdfError, ValueError, KeyError, TypeError, AttributeError) as error:
		raise PdfInvalid(f"Not a readable PDF: {error}") from error


def extract_pages(pdf: bytes, first: int, last: int | None = None) -> bytes:
	"""Pages first..last (1-based, inclusive) as a new PDF. Used to download the certificate pages."""
	reader = open_pdf(pdf)
	last = last or len(reader.pages)
	if first < 1 or first > last or last > len(reader.pages):
		raise PdfInvalid(f"Pages {first} to {last} are not in a {len(reader.pages)} page PDF")
	writer = PdfWriter()
	for index in range(first - 1, last):
		writer.add_page(reader.pages[index])
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()
