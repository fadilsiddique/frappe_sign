"""Translate pdf/ and crypto/ errors into the domain errors of exceptions.py (DESIGN 6)."""

from __future__ import annotations

from typing import NoReturn

import frappe
from frappe import _

from frappe_sign.exceptions import FieldValidationError
from frappe_sign.pdf.types import (
	PdfEncrypted,
	PdfError,
	PdfInvalid,
	PdfRenderFailed,
	PdfTooLarge,
	PdfTooManyPages,
)


def pdf_message(error: PdfError) -> str:
	if isinstance(error, PdfEncrypted):
		return _("The PDF is password protected. Remove the password and upload it again.")
	if isinstance(error, PdfTooLarge):
		return _("The PDF is too large. {0}").format(str(error))
	if isinstance(error, PdfTooManyPages):
		return _("The PDF has too many pages. {0}").format(str(error))
	if isinstance(error, PdfRenderFailed):
		return _("The Print Format could not be rendered as a PDF: {0}").format(str(error))
	if isinstance(error, PdfInvalid):
		return _("The file is not a readable PDF.")
	return _("The PDF could not be processed: {0}").format(str(error))


def raise_pdf_error(error: PdfError) -> NoReturn:
	frappe.throw(pdf_message(error), FieldValidationError)
	raise error  # frappe.throw always raises; this keeps type checkers informed.
