"""Stage 2: reject encrypted PDFs, enforce caps, strip JavaScript, actions, attachments and forms.

The output is rebuilt from the pages alone, so catalog level content (document JavaScript,
OpenAction, AcroForm, embedded files, outlines) never reaches it. Pages lose their additional
actions, form widgets and attachment or media annotations. Links stay only when they open a URI
or jump inside the document.
"""

from __future__ import annotations

import hashlib
import io

from pypdf import PdfWriter
from pypdf._page import PageObject
from pypdf.errors import PyPdfError
from pypdf.generic import ArrayObject, DictionaryObject, NameObject

from frappe_sign.pdf.pages import metric_of, open_pdf
from frappe_sign.pdf.types import PdfInvalid, PdfTooLarge, PdfTooManyPages, SanitizedPdf

DROPPED_ANNOTATIONS = {"/Widget", "/FileAttachment", "/Screen", "/Movie", "/Sound", "/RichMedia", "/3D"}
SAFE_ACTIONS = {"/URI", "/GoTo"}


def sanitize(pdf: bytes, *, max_bytes: int, max_pages: int) -> SanitizedPdf:
	if len(pdf) > max_bytes:
		raise PdfTooLarge(f"PDF is {len(pdf)} bytes; the limit is {max_bytes}")
	reader = open_pdf(pdf)
	try:
		count = len(reader.pages)
		if count == 0:
			raise PdfInvalid("PDF has no pages")
		if count > max_pages:
			raise PdfTooManyPages(f"PDF has {count} pages; the limit is {max_pages}")
		writer = PdfWriter()
		metrics = []
		for number, page in enumerate(reader.pages, start=1):
			added = writer.add_page(page)
			strip_page(added)
			metrics.append(metric_of(added, number))
		out = io.BytesIO()
		writer.write(out)
	except (PyPdfError, ValueError, KeyError, TypeError, AttributeError, RecursionError) as error:
		raise PdfInvalid(f"Not a readable PDF: {error}") from error
	data = out.getvalue()
	return SanitizedPdf(data=data, sha256=hashlib.sha256(data).hexdigest(), metrics=metrics)


def strip_page(page: PageObject) -> None:
	page.pop(NameObject("/AA"), None)
	annotations = page.get("/Annots")
	if annotations is None:
		return
	kept = ArrayObject()
	for reference in annotations.get_object():
		annotation = reference.get_object()
		if not isinstance(annotation, DictionaryObject) or not is_safe_annotation(annotation):
			continue
		annotation.pop(NameObject("/AA"), None)
		kept.append(reference)
	if kept:
		page[NameObject("/Annots")] = kept
	else:
		del page["/Annots"]


def is_safe_annotation(annotation: DictionaryObject) -> bool:
	if annotation.get("/Subtype") in DROPPED_ANNOTATIONS:
		return False
	action = annotation.get("/A")
	if action is None:
		return True
	action = action.get_object()
	# Chained actions (/Next) could hide a script behind a safe first step.
	return action.get("/S") in SAFE_ACTIONS and "/Next" not in action
