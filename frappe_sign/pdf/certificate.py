"""Stage 5: render the certificate of completion and append it.

The certificate is drawn with reportlab platypus from a CertificateData value, so this stage is
pure like the overlay and shares its fonts and Arabic shaping. It lists the envelope, the frozen
PDF hash, each signer with the hash of the intermediate PDF they completed, the audit trail and a
QR code to /sign-verify. Services format dates and translate labels before calling it.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

import qrcode
from pypdf import PdfWriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

from frappe_sign.pdf.pages import open_pdf
from frappe_sign.pdf.text import FontNames, register_fonts, visual_runs
from frappe_sign.pdf.types import FontSet

DEFAULT_BRAND = "#0f766e"
MARGIN = 16 * mm
HEADER_HEIGHT = 22 * mm
INK = colors.HexColor("#1f2937")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")

DEFAULT_LABELS = {
	"heading": "Certificate of Completion",
	"envelope": "Envelope",
	"document": "Document",
	"company": "Company",
	"sender": "Sent by",
	"sent_at": "Sent",
	"completed_at": "Completed",
	"original_sha256": "Original PDF SHA-256",
	"audit_head": "Audit chain head",
	"signers": "Signers",
	"name": "Name",
	"role": "Role",
	"signed_at": "Signed",
	"ip": "IP address",
	"intermediate_sha256": "PDF SHA-256 at signing",
	"events": "Audit trail",
	"at": "Time",
	"event": "Event",
	"actor": "By",
	"verify": "Scan or open the link to verify this document:",
	"page": "Page {0}",
	"sealed_note": "The completed PDF, including this certificate, is sealed with a PAdES signature.",
}


@dataclass(frozen=True)
class CertificateSigner:
	name: str
	email: str
	role: str
	kind: str
	signed_at: str
	ip: str | None = None
	intermediate_sha256: str | None = None
	signature: bytes | None = None


@dataclass(frozen=True)
class CertificateEvent:
	at: str
	event: str
	actor: str | None = None
	ip: str | None = None


@dataclass(frozen=True)
class CertificateData:
	envelope: str
	title: str
	original_sha256: str
	audit_head: str
	verify_url: str
	completed_at: str
	sent_at: str = ""
	sender: str = ""
	company: str | None = None
	brand_color: str | None = None
	logo: bytes | None = None
	legal_footer: str | None = None
	signers: list[CertificateSigner] = field(default_factory=list)
	events: list[CertificateEvent] = field(default_factory=list)
	labels: dict[str, str] = field(default_factory=dict)

	def label(self, key: str) -> str:
		return self.labels.get(key) or DEFAULT_LABELS[key]


def append_certificate(pdf: bytes, certificate_pdf: bytes) -> bytes:
	writer = PdfWriter(clone_from=open_pdf(pdf))
	writer.append(open_pdf(certificate_pdf))
	out = io.BytesIO()
	writer.write(out)
	return out.getvalue()


def render_certificate(data: CertificateData, fonts: FontSet) -> bytes:
	names = register_fonts(fonts)
	brand = brand_colour(data.brand_color)
	buffer = io.BytesIO()
	document = SimpleDocTemplate(
		buffer,
		pagesize=A4,
		leftMargin=MARGIN,
		rightMargin=MARGIN,
		topMargin=MARGIN + HEADER_HEIGHT,
		bottomMargin=MARGIN + 8 * mm,
		title=f"{data.label('heading')}: {data.envelope}",
		author=data.company or "",
		invariant=1,
	)
	styles = Styles(names, brand)

	def decorate(canvas: Canvas, doc: SimpleDocTemplate) -> None:
		draw_frame(canvas, doc, data, names, brand)

	document.build(story(data, styles, document.width), onFirstPage=decorate, onLaterPages=decorate)
	return buffer.getvalue()


def brand_colour(value: str | None) -> colors.Color:
	try:
		return colors.HexColor(value or DEFAULT_BRAND)
	except (ValueError, TypeError):
		return colors.HexColor(DEFAULT_BRAND)


class Styles:
	def __init__(self, names: FontNames, brand: colors.Color) -> None:
		self.names = names
		self.heading = ParagraphStyle(
			"heading", fontName=names.latin_bold, fontSize=12, leading=16, textColor=brand, spaceBefore=10
		)
		self.label = ParagraphStyle("label", fontName=names.latin, fontSize=8, leading=10, textColor=MUTED)
		self.value = ParagraphStyle(
			"value", fontName=names.latin, fontSize=9, leading=12, textColor=INK, wordWrap="CJK"
		)
		self.small = ParagraphStyle(
			"small", fontName=names.latin, fontSize=7.5, leading=9.5, textColor=INK, wordWrap="CJK"
		)
		# Hashes break anywhere (wordWrap CJK); words in cells break only at spaces.
		self.cell = ParagraphStyle("cell", fontName=names.latin, fontSize=7.5, leading=9.5, textColor=INK)
		self.header = ParagraphStyle(
			"header", fontName=names.latin_bold, fontSize=8, leading=10, textColor=MUTED
		)

	def text(self, value: str | None, style: ParagraphStyle | None = None) -> Paragraph:
		return Paragraph(markup(value or "", self.names, bold=style is self.header), style or self.value)


def markup(value: str, names: FontNames, bold: bool = False) -> str:
	"""Paragraph markup with each script run in its font, Arabic shaped and in visual order."""
	latin = names.latin_bold if bold else names.latin
	return "".join(
		f'<font name="{names.arabic if arabic else latin}">{escape(text)}</font>'
		for text, arabic in visual_runs(value)
	)


def story(data: CertificateData, styles: Styles, width: float) -> list[Flowable]:
	return [
		summary(data, styles, width),
		Paragraph(escape(data.label("signers")), styles.heading),
		signers_table(data, styles, width),
		Paragraph(escape(data.label("events")), styles.heading),
		events_table(data, styles, width),
		Spacer(1, 4 * mm),
		Paragraph(escape(data.label("sealed_note")), styles.label),
	]


def summary(data: CertificateData, styles: Styles, width: float) -> Table:
	rows = [
		("envelope", data.envelope),
		("document", data.title),
		("company", data.company),
		("sender", data.sender),
		("sent_at", data.sent_at),
		("completed_at", data.completed_at),
		("original_sha256", data.original_sha256),
		("audit_head", data.audit_head),
	]
	details = Table(
		[[styles.text(data.label(key), styles.label), styles.text(value)] for key, value in rows if value],
		colWidths=[38 * mm, width - 38 * mm - 42 * mm],
	)
	details.setStyle(
		TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)])
	)
	verify = Table(
		[
			[qr_image(data.verify_url, 32 * mm)],
			[styles.text(data.label("verify"), styles.label)],
			[styles.text(data.verify_url, styles.small)],
		],
		colWidths=[40 * mm],
	)
	verify.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER")]))
	layout = Table([[details, verify]], colWidths=[width - 42 * mm, 42 * mm])
	layout.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
	return layout


def signers_table(data: CertificateData, styles: Styles, width: float) -> Table:
	header: list[Flowable] = [
		styles.text(data.label(key), styles.header)
		for key in ("name", "role", "signed_at", "intermediate_sha256")
	]
	header.insert(0, Paragraph("", styles.header))
	rows: list[list[Flowable]] = [header]
	for signer in data.signers:
		identity = Table(
			[
				[styles.text(signer.name)],
				[styles.text(signer.email, styles.small)],
				[styles.text(signer.ip, styles.small)],
			],
			colWidths=[None],
		)
		identity.setStyle(
			TableStyle(
				[
					("LEFTPADDING", (0, 0), (-1, -1), 0),
					("TOPPADDING", (0, 0), (-1, -1), 0),
					("BOTTOMPADDING", (0, 0), (-1, -1), 1),
				]
			)
		)
		rows.append(
			[
				signature_image(signer.signature, 30 * mm, 12 * mm),
				identity,
				styles.text(f"{signer.role} ({signer.kind})", styles.cell),
				styles.text(signer.signed_at, styles.cell),
				styles.text(signer.intermediate_sha256, styles.small),
			]
		)
	return grid(rows, [32 * mm, 44 * mm, 30 * mm, 26 * mm, width - 132 * mm])


def events_table(data: CertificateData, styles: Styles, width: float) -> Table:
	header: list[Flowable] = [
		styles.text(data.label(key), styles.header) for key in ("at", "event", "actor", "ip")
	]
	rows: list[list[Flowable]] = [header]
	rows.extend(
		[
			styles.text(event.at, styles.cell),
			styles.text(event.event, styles.cell),
			styles.text(event.actor, styles.small),
			styles.text(event.ip, styles.cell),
		]
		for event in data.events
	)
	return grid(rows, [42 * mm, 34 * mm, width - 106 * mm, 30 * mm])


def grid(rows: list[list[Flowable]], widths: list[float]) -> Table:
	table = Table(rows, colWidths=widths, repeatRows=1)
	table.setStyle(
		TableStyle(
			[
				("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
				("LINEBELOW", (0, 0), (-1, -1), 0.5, RULE),
				("TOPPADDING", (0, 0), (-1, -1), 3),
				("BOTTOMPADDING", (0, 0), (-1, -1), 3),
			]
		)
	)
	return table


def signature_image(data: bytes | None, width: float, height: float) -> Flowable:
	if not data:
		return Spacer(width, height)
	reader = ImageReader(io.BytesIO(data))
	image_width, image_height = reader.getSize()
	scale = min(width / image_width, height / image_height)
	return Image(io.BytesIO(data), width=image_width * scale, height=image_height * scale)


def qr_image(url: str, size: float) -> Image:
	code = qrcode.QRCode(border=1, error_correction=qrcode.constants.ERROR_CORRECT_M)
	code.add_data(url)
	code.make(fit=True)
	out = io.BytesIO()
	code.make_image(fill_color="black", back_color="white").save(out)
	out.seek(0)
	return Image(out, width=size, height=size)


def draw_frame(
	canvas: Canvas, doc: SimpleDocTemplate, data: CertificateData, names: FontNames, brand: colors.Color
) -> None:
	page_width, page_height = A4
	canvas.saveState()
	canvas.setFillColor(brand)
	canvas.rect(0, page_height - 6 * mm, page_width, 6 * mm, stroke=0, fill=1)
	top = page_height - MARGIN - 4 * mm
	x = MARGIN
	if data.logo:
		logo = ImageReader(io.BytesIO(data.logo))
		logo_width, logo_height = logo.getSize()
		height = 10 * mm
		width = min(logo_width * height / logo_height, 50 * mm)
		canvas.drawImage(logo, x, top - height + 2 * mm, width, height, mask="auto", preserveAspectRatio=True)
		x += width + 5 * mm
	canvas.setFillColor(INK)
	canvas.setFont(names.latin_bold, 15)
	canvas.drawString(x, top - 4 * mm, data.label("heading"))
	canvas.setFont(names.latin, 8)
	canvas.setFillColor(MUTED)
	canvas.drawRightString(page_width - MARGIN, top - 4 * mm, data.envelope)
	canvas.setStrokeColor(RULE)
	canvas.line(MARGIN, top - 9 * mm, page_width - MARGIN, top - 9 * mm)
	canvas.drawString(MARGIN, MARGIN, (data.legal_footer or "")[:160])
	canvas.drawRightString(page_width - MARGIN, MARGIN, data.label("page").format(doc.page))
	canvas.restoreState()
