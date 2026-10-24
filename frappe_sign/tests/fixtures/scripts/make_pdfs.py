"""Generate the fixture PDFs in tests/fixtures/pdfs/ and tests/fixtures/coords.json.

Run from the bench directory:

    env/bin/python apps/frappe_sign/frappe_sign/tests/fixtures/scripts/make_pdfs.py

Output is deterministic (reportlab invariant mode, no dates), except encrypted.pdf, whose
encryption salt is random by design. check_coords.py checks coords.json against pdfium.
"""

import io
import json
import random
import sys
from dataclasses import dataclass
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
	ArrayObject,
	DictionaryObject,
	FloatObject,
	NameObject,
	NumberObject,
	RectangleObject,
	TextStringObject,
)
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

FIXTURES_DIR = Path(__file__).resolve().parents[1]
APP_PACKAGE = Path(__file__).resolve().parents[3]
ARABIC_FONT = APP_PACKAGE / "pdf" / "fonts" / "NotoNaskhArabic-Regular.ttf"

ENCRYPTED_USER_PASSWORD = "fixture-user"
ENCRYPTED_OWNER_PASSWORD = "fixture-owner"
MANY_PAGES = 150

# Normalized rects (x, y, w, h; 0..1, top-left origin, visible page box) drawn as filled boxes in
# each geometric fixture, in a colour pdfium can find again (check_coords.py).
CASES = (
	("top_left", (0.05, 0.05, 0.30, 0.10), (1, 0, 0)),
	("bottom_right", (0.60, 0.85, 0.35, 0.10), (0, 1, 0)),
	("center", (0.40, 0.45, 0.20, 0.10), (0, 0, 1)),
)


@dataclass(frozen=True)
class Geometry:
	file: str
	description: str
	mediabox: tuple[float, float, float, float]
	cropbox: tuple[float, float, float, float]
	rotation: int


A4_BOX = (0.0, 0.0, A4[0], A4[1])
LETTER_BOX = (0.0, 0.0, LETTER[0], LETTER[1])

GEOMETRIES = (
	Geometry("a4_simple.pdf", "A4 portrait, no rotation, CropBox = MediaBox", A4_BOX, A4_BOX, 0),
	Geometry("letter_simple.pdf", "US Letter portrait, no rotation", LETTER_BOX, LETTER_BOX, 0),
	Geometry("rotated_90.pdf", "A4 page with /Rotate 90 (shown landscape)", A4_BOX, A4_BOX, 90),
	Geometry(
		"offset_cropbox.pdf",
		"A4 MediaBox with a CropBox offset from the origin",
		A4_BOX,
		(40.0, 60.0, 520.0, 780.0),
		0,
	),
	Geometry(
		"rotated_270_cropbox.pdf",
		"US Letter with /Rotate 270 and an offset CropBox",
		LETTER_BOX,
		(36.0, 48.0, 576.0, 744.0),
		270,
	),
)


def display_size(geometry: Geometry) -> tuple[float, float]:
	x0, y0, x1, y1 = geometry.cropbox
	width, height = x1 - x0, y1 - y0
	return (height, width) if geometry.rotation in (90, 270) else (width, height)


def display_to_user(geometry: Geometry, x: float, y: float) -> tuple[float, float]:
	"""A point in the displayed page (points from the top-left) to PDF user space.

	/Rotate turns the page clockwise for display. This is the reference mapping that coords.json
	records; check_coords.py confirms it against pdfium.
	"""
	cx0, cy0, cx1, cy1 = geometry.cropbox
	match geometry.rotation:
		case 0:
			return cx0 + x, cy1 - y
		case 90:
			return cx0 + y, cy0 + x
		case 180:
			return cx1 - x, cy0 + y
		case 270:
			return cx1 - y, cy1 - x
	raise ValueError(f"unsupported rotation {geometry.rotation}")


def expected_pdf_rect(geometry: Geometry, rect: tuple[float, float, float, float]) -> list[float]:
	"""[llx, lly, urx, ury] in user space for a normalized rect."""
	display_width, display_height = display_size(geometry)
	x, y, w, h = rect
	corners = [
		display_to_user(geometry, cx * display_width, cy * display_height)
		for cx in (x, x + w)
		for cy in (y, y + h)
	]
	xs, ys = [c[0] for c in corners], [c[1] for c in corners]
	return [round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4)]


def new_canvas(buffer: io.BytesIO, pagesize: tuple[float, float]) -> canvas.Canvas:
	return canvas.Canvas(buffer, pagesize=pagesize, invariant=1, pageCompression=1)


def write(writer: PdfWriter, path: Path) -> None:
	with path.open("wb") as handle:
		writer.write(handle)


def make_geometry(geometry: Geometry, path: Path) -> dict:
	buffer = io.BytesIO()
	media_width, media_height = geometry.mediabox[2], geometry.mediabox[3]
	pdf = new_canvas(buffer, (media_width, media_height))
	cx0, cy0 = geometry.cropbox[0], geometry.cropbox[1]
	pdf.setFont("Helvetica", 9)
	pdf.drawString(cx0 + 150, cy0 + 300, f"frappe_sign fixture: {geometry.file}")
	cases = []
	for name, rect, color in CASES:
		llx, lly, urx, ury = expected_pdf_rect(geometry, rect)
		pdf.setFillColorRGB(*color)
		pdf.rect(llx, lly, urx - llx, ury - lly, stroke=0, fill=1)
		cases.append(
			{
				"name": name,
				"page": 1,
				"rect": dict(zip("xywh", rect, strict=True)),
				"pdf_rect": [llx, lly, urx, ury],
				"color": list(color),
			}
		)
	pdf.showPage()
	pdf.save()

	writer = PdfWriter(clone_from=PdfReader(io.BytesIO(buffer.getvalue())))
	page = writer.pages[0]
	page.cropbox = RectangleObject(geometry.cropbox)
	if geometry.rotation:
		page.rotate(geometry.rotation)
	write(writer, path)

	display_width, display_height = display_size(geometry)
	return {
		"description": geometry.description,
		"pages": [
			{
				"page": 1,
				"mediabox": [round(v, 4) for v in geometry.mediabox],
				"cropbox": [round(v, 4) for v in geometry.cropbox],
				"rotation": geometry.rotation,
				"display_width": round(display_width, 4),
				"display_height": round(display_height, 4),
			}
		],
		"cases": cases,
	}


def make_scanned(path: Path) -> None:
	"""One page that is only a raster image, like a scan: no text layer."""
	rng = random.Random(16)
	image = Image.new("L", (827, 1169), 250)
	draw = ImageDraw.Draw(image)
	for row in range(28):
		top = 110 + row * 36
		draw.rectangle((80, top, 80 + rng.randint(420, 660), top + 12), fill=rng.randint(30, 70))
	for _ in range(6000):
		draw.point((rng.randrange(827), rng.randrange(1169)), fill=rng.randint(150, 220))
	buffer = io.BytesIO()
	pdf = new_canvas(buffer, A4)
	pdf.drawImage(ImageReader(image), 0, 0, width=A4[0], height=A4[1])
	pdf.showPage()
	pdf.save()
	path.write_bytes(buffer.getvalue())


def make_many_pages(path: Path) -> None:
	buffer = io.BytesIO()
	pdf = new_canvas(buffer, A4)
	for number in range(1, MANY_PAGES + 1):
		pdf.setFont("Helvetica", 11)
		pdf.drawString(72, A4[1] - 72, f"Page {number} of {MANY_PAGES}")
		pdf.line(72, A4[1] - 80, A4[0] - 72, A4[1] - 80)
		pdf.showPage()
	pdf.save()
	path.write_bytes(buffer.getvalue())


def simple_page(text: str) -> PdfWriter:
	buffer = io.BytesIO()
	pdf = new_canvas(buffer, A4)
	pdf.setFont("Helvetica", 12)
	pdf.drawString(72, A4[1] - 72, text)
	pdf.showPage()
	pdf.save()
	return PdfWriter(clone_from=PdfReader(io.BytesIO(buffer.getvalue())))


def make_encrypted(path: Path) -> None:
	writer = simple_page("frappe_sign fixture: encrypted")
	writer.encrypt(ENCRYPTED_USER_PASSWORD, ENCRYPTED_OWNER_PASSWORD, algorithm="AES-256")
	write(writer, path)


def javascript_action(script: str) -> DictionaryObject:
	return DictionaryObject(
		{
			NameObject("/S"): NameObject("/JavaScript"),
			NameObject("/JS"): TextStringObject(script),
		}
	)


def make_active_content(path: Path) -> None:
	"""Everything sanitize.py must strip: JavaScript, OpenAction, AA, EmbeddedFiles, AcroForm."""
	writer = simple_page("frappe_sign fixture: active content")
	writer.add_attachment("payload.txt", b"frappe_sign fixture attachment\n")
	# Built by hand: pypdf's add_js names the script with a random UUID, which breaks reproducibility.
	names = writer.root_object["/Names"]
	script = writer._add_object(javascript_action("app.alert('frappe_sign fixture: document JavaScript');"))
	names[NameObject("/JavaScript")] = DictionaryObject(
		{NameObject("/Names"): ArrayObject([TextStringObject("fixture"), script])}
	)
	writer.root_object[NameObject("/OpenAction")] = writer._add_object(
		javascript_action("app.alert('frappe_sign fixture: OpenAction');")
	)
	page = writer.pages[0]
	page[NameObject("/AA")] = DictionaryObject(
		{NameObject("/O"): javascript_action("app.alert('frappe_sign fixture: page open');")}
	)

	field = DictionaryObject(
		{
			NameObject("/Type"): NameObject("/Annot"),
			NameObject("/Subtype"): NameObject("/Widget"),
			NameObject("/FT"): NameObject("/Tx"),
			NameObject("/T"): TextStringObject("fixture_field"),
			NameObject("/Rect"): ArrayObject([FloatObject(v) for v in (72, 600, 300, 624)]),
			NameObject("/F"): NumberObject(4),
		}
	)
	field_ref = writer._add_object(field)
	field[NameObject("/P")] = page.indirect_reference
	page[NameObject("/Annots")] = ArrayObject([field_ref])
	writer.root_object[NameObject("/AcroForm")] = writer._add_object(
		DictionaryObject({NameObject("/Fields"): ArrayObject([field_ref])})
	)
	write(writer, path)


def shape_arabic(text: str) -> str:
	"""reportlab does not shape Arabic: join letters, then reorder for display (DESIGN 6)."""
	return get_display(arabic_reshaper.reshape(text))


def make_arabic(path: Path) -> None:
	pdfmetrics.registerFont(TTFont("NotoNaskhArabic", str(ARABIC_FONT)))
	buffer = io.BytesIO()
	pdf = new_canvas(buffer, A4)
	pdf.setFont("Helvetica", 14)
	pdf.drawString(72, A4[1] - 72, "Sales contract")
	pdf.setFont("NotoNaskhArabic", 16)
	right = A4[0] - 72
	for row, line in enumerate(("عقد بيع", "اسم العميل: أحمد خان", "رقم العقد 2026-001")):
		pdf.drawRightString(right, A4[1] - 120 - row * 32, shape_arabic(line))
	pdf.showPage()
	pdf.save()
	path.write_bytes(buffer.getvalue())


OTHER_FIXTURES = {
	"scanned_image.pdf": make_scanned,
	"many_pages_150.pdf": make_many_pages,
	"encrypted.pdf": make_encrypted,
	"with_javascript.pdf": make_active_content,
	"arabic_text.pdf": make_arabic,
}


def generate(out_dir: Path = FIXTURES_DIR) -> None:
	pdf_dir = out_dir / "pdfs"
	pdf_dir.mkdir(parents=True, exist_ok=True)
	fixtures = {geometry.file: make_geometry(geometry, pdf_dir / geometry.file) for geometry in GEOMETRIES}
	for file, make in OTHER_FIXTURES.items():
		make(pdf_dir / file)
	coords = {
		"version": 1,
		"description": (
			"Normalized field rects (x, y, w, h in 0..1, top-left origin, visible page box after CropBox "
			"and /Rotate) and the PDF user space rect [llx, lly, urx, ury] each must convert to. Shared "
			"by the Python and Vitest coordinate tests. Generated by scripts/make_pdfs.py."
		),
		"fixtures": fixtures,
	}
	(out_dir / "coords.json").write_text(json.dumps(coords, indent=2) + "\n")


if __name__ == "__main__":
	generate(Path(sys.argv[1]) if len(sys.argv) > 1 else FIXTURES_DIR)
	print(f"Fixtures written to {FIXTURES_DIR if len(sys.argv) < 2 else sys.argv[1]}")
