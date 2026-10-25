"""Stage 1: render a Print Format with frappe.get_print(..., as_pdf=True), or take uploaded bytes.

get_print uses the Print Format's own `pdf_generator` (wkhtmltopdf or chrome) when
`frappe.local.form_dict` has none, so render() never passes one (D5). In v16.0.0, get_print writes
`pdf_generator` to form_dict and does not restore it: a stale value would pick the generator of an
earlier render in the same request or job. render() removes it for the call and restores the
caller's form_dict afterwards.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import frappe

from frappe_sign.pdf.types import PdfRenderFailed

DEFAULT_GENERATOR = "wkhtmltopdf"
# Generators whose output the anchor tests cover (ARCHITECTURE, Compatibility).
TESTED_GENERATORS = ("wkhtmltopdf", "chrome")
# Per render: anchor sizes declared by sign_field() and the next `n` per role and field type.
ANCHORS = "frappe_sign_anchors"


@dataclass(frozen=True)
class RenderedPrint:
	pdf: bytes
	generator: str
	# Marker -> (width, height) in mm, as sign_field() declared it while the Print Format rendered.
	declared: dict[str, tuple[float, float]] = field(default_factory=dict)


def render_print(doctype: str, name: str, print_format: str | None, letter_head: str | None) -> bytes:
	return render(doctype, name, print_format, letter_head).pdf


def render(doctype: str, name: str, print_format: str | None, letter_head: str | None) -> RenderedPrint:
	"""The Print Format as PDF bytes. The session user needs print permission on the document."""
	local = frappe.local
	saved = local.form_dict
	local.form_dict = frappe._dict({key: value for key, value in saved.items() if key != "pdf_generator"})
	registry = start_anchor_registry()
	try:
		pdf = frappe.get_print(
			doctype, name, print_format or None, letterhead=letter_head or None, as_pdf=True
		)
	except frappe.PermissionError:
		raise
	except Exception as error:
		raise PdfRenderFailed(f"{print_format or 'Standard'}: {error}") from error
	finally:
		local.form_dict = saved
	if not isinstance(pdf, bytes) or not pdf.startswith(b"%PDF"):
		raise PdfRenderFailed(f"{print_format or 'Standard'} did not render to a PDF")
	return RenderedPrint(pdf=pdf, generator=print_generator(print_format), declared=dict(registry["sizes"]))


def print_generator(print_format: str | None) -> str:
	"""The generator get_print uses for this Print Format: its own setting, else wkhtmltopdf."""
	if not print_format or print_format == "Standard":
		return DEFAULT_GENERATOR
	return frappe.get_cached_value("Print Format", print_format, "pdf_generator") or DEFAULT_GENERATOR


def start_anchor_registry() -> dict[str, Any]:
	registry: dict[str, Any] = {"sizes": {}, "counts": {}}
	setattr(frappe.local, ANCHORS, registry)
	return registry


def anchor_registry() -> dict[str, Any]:
	"""The current render's registry. A Desk print preview, outside render(), gets one per request."""
	registry = getattr(frappe.local, ANCHORS, None)
	return registry if registry is not None else start_anchor_registry()


def next_anchor_number(role: str, field_type: str) -> int:
	counts = anchor_registry()["counts"]
	counts[(role, field_type)] = counts.get((role, field_type), 0) + 1
	return int(counts[(role, field_type)])


def declare_anchor(tag: str, width_mm: float, height_mm: float) -> None:
	anchor_registry()["sizes"][tag] = (width_mm, height_mm)
