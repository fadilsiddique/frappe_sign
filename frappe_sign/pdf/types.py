"""Dataclasses, PdfError hierarchy and the one normalized <-> PDF user space conversion (D7).

Coordinates in three spaces:

- Normalized: a Rect with x, y, w, h in 0..1, top-left origin, relative to the visible page
  (CropBox, after /Rotate). This is what templates and envelopes store.
- Display: points from the top-left of the visible page, as a reader shows it.
- User space: PDF points in the page's own coordinate system, before /Rotate.

frontend/src/shared/coords.ts mirrors these functions. Both sides are tested against
tests/fixtures/coords.json; change them together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ROTATIONS = (0, 90, 180, 270)


class PdfError(Exception):
	"""Base error of the pdf/ stages. Services translate these to exceptions.py errors."""

	code = "pdf_error"


class PdfInvalid(PdfError):
	code = "pdf_invalid"


class PdfEncrypted(PdfError):
	code = "pdf_encrypted"


class PdfTooLarge(PdfError):
	code = "pdf_too_large"


class PdfTooManyPages(PdfError):
	code = "pdf_too_many_pages"


class AnchorNotFound(PdfError):
	code = "anchor_not_found"


class SealError(PdfError):
	code = "seal_error"


class PdfRenderFailed(PdfError):
	"""The Print Format could not be rendered to a PDF (template error, generator missing)."""

	code = "pdf_render_failed"


@dataclass(frozen=True)
class Rect:
	"""Normalized rect: 0..1, top-left origin, visible page box."""

	x: float
	y: float
	w: float
	h: float


@dataclass(frozen=True)
class Box:
	"""PDF user space rect: lower-left and upper-right corners in points."""

	llx: float
	lly: float
	urx: float
	ury: float

	def as_list(self) -> list[float]:
		return [self.llx, self.lly, self.urx, self.ury]


@dataclass(frozen=True)
class PageMetric:
	"""Size of one page's CropBox in points, its origin and its clockwise /Rotate."""

	page: int
	width: float
	height: float
	rotation: int = 0
	left: float = 0.0
	bottom: float = 0.0

	def __post_init__(self) -> None:
		rotation = self.rotation % 360
		if rotation not in ROTATIONS:
			raise PdfInvalid(f"Page {self.page}: /Rotate {self.rotation} is not a multiple of 90")
		object.__setattr__(self, "rotation", rotation)

	@property
	def display_width(self) -> float:
		return self.height if self.rotation in (90, 270) else self.width

	@property
	def display_height(self) -> float:
		return self.width if self.rotation in (90, 270) else self.height

	def to_dict(self) -> dict[str, float | int]:
		return {
			"page": self.page,
			"width": self.width,
			"height": self.height,
			"rotation": self.rotation,
			"left": self.left,
			"bottom": self.bottom,
		}

	@classmethod
	def from_dict(cls, data: dict[str, Any]) -> PageMetric:
		return cls(
			page=int(data["page"]),
			width=float(data["width"]),
			height=float(data["height"]),
			rotation=int(data.get("rotation") or 0),
			left=float(data.get("left") or 0),
			bottom=float(data.get("bottom") or 0),
		)


@dataclass(frozen=True)
class Anchor:
	"""A [[fs:<role>:<field_type>:<n>]] marker found in a rendered PDF (DESIGN 4.2)."""

	tag: str
	role: str
	field_type: str
	n: int
	page: int
	rect: Rect


@dataclass(frozen=True)
class PlacedField:
	"""A field with its final page and rect, ready for the overlay.

	`value` is display text (Text, Number, Date Signed, Full Name, Email, Dropdown) or "1"/"0"
	for a Checkbox. Image fields (Signature, Initials, Company Stamp) take their PNG or JPEG from
	the `captures` argument of overlay.apply_fields, keyed by `key`. `mask` paints the field area
	white first, which hides anchor markers.
	"""

	key: str
	field_type: str
	page: int
	rect: Rect
	value: str | None = None
	font_size: float = 11.0
	mask: bool = False


@dataclass(frozen=True)
class FontSet:
	"""TrueType font files embedded in overlays and certificates."""

	latin: str
	latin_bold: str
	arabic: str


@dataclass(frozen=True)
class SanitizedPdf:
	data: bytes
	sha256: str
	metrics: list[PageMetric] = field(default_factory=list)

	@property
	def page_count(self) -> int:
		return len(self.metrics)


def display_to_user(metric: PageMetric, x: float, y: float) -> tuple[float, float]:
	"""A display point (points from the shown top-left) to PDF user space.

	/Rotate turns the page clockwise for display.
	"""
	left, bottom = metric.left, metric.bottom
	right, top = left + metric.width, bottom + metric.height
	match metric.rotation:
		case 90:
			return left + y, bottom + x
		case 180:
			return right - x, bottom + y
		case 270:
			return right - y, top - x
	return left + x, top - y


def user_to_display(metric: PageMetric, ux: float, uy: float) -> tuple[float, float]:
	left, bottom = metric.left, metric.bottom
	right, top = left + metric.width, bottom + metric.height
	match metric.rotation:
		case 90:
			return uy - bottom, ux - left
		case 180:
			return right - ux, uy - bottom
		case 270:
			return top - uy, right - ux
	return ux - left, top - uy


def normalized_to_pdf(metric: PageMetric, rect: Rect) -> Box:
	corners = [
		display_to_user(metric, cx * metric.display_width, cy * metric.display_height)
		for cx in (rect.x, rect.x + rect.w)
		for cy in (rect.y, rect.y + rect.h)
	]
	xs, ys = [c[0] for c in corners], [c[1] for c in corners]
	return Box(min(xs), min(ys), max(xs), max(ys))


def pdf_to_normalized(metric: PageMetric, box: Box) -> Rect:
	corners = [user_to_display(metric, ux, uy) for ux in (box.llx, box.urx) for uy in (box.lly, box.ury)]
	xs, ys = [c[0] for c in corners], [c[1] for c in corners]
	width, height = metric.display_width, metric.display_height
	return Rect(
		x=min(xs) / width,
		y=min(ys) / height,
		w=(max(xs) - min(xs)) / width,
		h=(max(ys) - min(ys)) / height,
	)


def display_matrix(metric: PageMetric) -> tuple[float, float, float, float, float, float]:
	"""PDF matrix [a b c d e f] from bottom-left display space (y up) to user space.

	The overlay draws each page upright at its display size with reportlab, then merges it with
	this matrix, so text stays upright on rotated pages.
	"""
	height = metric.display_height

	def to_user(u: float, v: float) -> tuple[float, float]:
		return display_to_user(metric, u, height - v)

	e, f = to_user(0, 0)
	ux, uy = to_user(1, 0)
	vx, vy = to_user(0, 1)
	return (ux - e, uy - f, vx - e, vy - f, e, f)
