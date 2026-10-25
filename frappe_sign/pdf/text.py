"""Text for overlays and certificates: fonts, Arabic shaping and script runs (DESIGN 6).

reportlab does not shape Arabic. Text with Arabic letters runs through arabic_reshaper (contextual
forms and ligatures) and python-bidi (visual order), then splits into runs: Arabic letters use
Noto Naskh Arabic, everything else Noto Sans. Both fonts are embedded.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import arabic_reshaper
from bidi.algorithm import get_display
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from frappe_sign.pdf.types import FontSet

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
ARABIC_RANGES = (
	(0x0600, 0x06FF),
	(0x0750, 0x077F),
	(0x08A0, 0x08FF),
	(0xFB50, 0xFDFF),
	(0xFE70, 0xFEFF),
)

# A run of text in visual order and whether it is drawn with the Arabic font.
Run = tuple[str, bool]


@dataclass(frozen=True)
class FontNames:
	"""reportlab names of a registered FontSet."""

	latin: str
	latin_bold: str
	arabic: str


def default_fonts() -> FontSet:
	return FontSet(
		latin=str(FONTS_DIR / "NotoSans-Regular.ttf"),
		latin_bold=str(FONTS_DIR / "NotoSans-Bold.ttf"),
		arabic=str(FONTS_DIR / "NotoNaskhArabic-Regular.ttf"),
	)


@cache
def register_font(path: str) -> str:
	"""Register a TrueType file with reportlab once and return its name."""
	stem = Path(path).stem.replace(" ", "")
	name = f"{stem}-{hashlib.sha256(path.encode()).hexdigest()[:8]}"
	pdfmetrics.registerFont(TTFont(name, path))
	return name


def register_fonts(fonts: FontSet) -> FontNames:
	return FontNames(
		latin=register_font(fonts.latin),
		latin_bold=register_font(fonts.latin_bold),
		arabic=register_font(fonts.arabic),
	)


def is_arabic_char(char: str) -> bool:
	code = ord(char)
	return any(start <= code <= end for start, end in ARABIC_RANGES)


def has_arabic(text: str) -> bool:
	return any(is_arabic_char(char) for char in text)


def is_rtl(text: str) -> bool:
	"""True when the first strongly directional character is right to left."""
	for char in text:
		direction = unicodedata.bidirectional(char)
		if direction in ("R", "AL"):
			return True
		if direction == "L":
			return False
	return False


def visual_runs(text: str) -> list[Run]:
	"""Shaped text in visual (left to right) order, split by font."""
	if not has_arabic(text):
		return [(text, False)] if text else []
	visual = get_display(arabic_reshaper.reshape(text))
	runs: list[Run] = []
	for char in visual:
		arabic = is_arabic_char(char)
		if runs and (runs[-1][1] == arabic or not char.strip()):
			runs[-1] = (runs[-1][0] + char, runs[-1][1])
		else:
			runs.append((char, arabic))
	return runs


def runs_width(runs: list[Run], names: FontNames, size: float, bold: bool = False) -> float:
	latin = names.latin_bold if bold else names.latin
	return sum(pdfmetrics.stringWidth(text, names.arabic if arabic else latin, size) for text, arabic in runs)
