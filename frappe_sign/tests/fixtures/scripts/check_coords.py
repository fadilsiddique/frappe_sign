"""Check coords.json against pdfium, which applies CropBox and /Rotate on its own.

Each geometric fixture has a filled box at every expected rect. This renders the page with pypdfium2
(test-only dependency), finds each box by colour and checks it sits at the normalized rect. So the
expected values come from an independent renderer, not from the code under test.

    env/bin/python apps/frappe_sign/frappe_sign/tests/fixtures/scripts/check_coords.py
"""

import json
import sys
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageChops

FIXTURES_DIR = Path(__file__).resolve().parents[1]
SCALE = 2
# Box edges are anti-aliased; allow two pixels at the render scale (one point).
TOLERANCE_PX = 2


def colour_mask(image: Image.Image, colour: list[int]) -> Image.Image:
	"""White where a pixel is close to the pure colour (each channel 0 or 1)."""
	masks = [
		channel.point(lambda v, on=bool(on): 255 if (v > 200 if on else v < 60) else 0)
		for channel, on in zip(image.split(), colour, strict=True)
	]
	mask = masks[0]
	for other in masks[1:]:
		mask = ImageChops.multiply(mask, other)
	return mask


def check(fixtures_dir: Path = FIXTURES_DIR) -> list[str]:
	coords = json.loads((fixtures_dir / "coords.json").read_text())
	problems = []
	for file, fixture in coords["fixtures"].items():
		document = pdfium.PdfDocument(fixtures_dir / "pdfs" / file)
		for metric in fixture["pages"]:
			page = document[metric["page"] - 1]
			image = page.render(scale=SCALE).to_pil().convert("RGB")
			width, height = image.size
			expected_size = (metric["display_width"] * SCALE, metric["display_height"] * SCALE)
			if abs(width - expected_size[0]) > 1 or abs(height - expected_size[1]) > 1:
				problems.append(f"{file}: rendered {image.size}, expected {expected_size}")
				continue
			for case in fixture["cases"]:
				if case["page"] != metric["page"]:
					continue
				box = colour_mask(image, case["color"]).getbbox()
				if not box:
					problems.append(f"{file} {case['name']}: box not found")
					continue
				rect = case["rect"]
				expected = (
					rect["x"] * width,
					rect["y"] * height,
					(rect["x"] + rect["w"]) * width,
					(rect["y"] + rect["h"]) * height,
				)
				if any(abs(a - b) > TOLERANCE_PX for a, b in zip(box, expected, strict=True)):
					problems.append(f"{file} {case['name']}: found {box}, expected {expected}")
		document.close()
	return problems


if __name__ == "__main__":
	found = check(Path(sys.argv[1]) if len(sys.argv) > 1 else FIXTURES_DIR)
	print("\n".join(found) or "coords.json matches pdfium for every fixture")
	sys.exit(1 if found else 0)
