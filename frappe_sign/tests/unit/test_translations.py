"""Arabic translations (P3.5): the CSV is complete, consistent and covers every string the app shows."""

import csv
import re
from pathlib import Path

import frappe
from frappe.tests import UnitTestCase

APP = Path(frappe.get_app_path("frappe_sign"))
FRONTEND = APP.parent / "frontend" / "src"
PLACEHOLDER = re.compile(r"\{\d+\}")
JS_STRING = re.compile(r"""\b__\(\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)"|`((?:[^`\\$]|\\.)*)`)""", re.S)
# Only a complete literal: an implicit concatenation ("a" "b") is skipped, its parts are not strings.
PY_STRING = re.compile(r"""\b_\(\s*(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)')(?=\s*[,)])""")


def rows() -> list[list[str]]:
	with open(APP / "translations" / "ar.csv", encoding="utf-8", newline="") as handle:
		return list(csv.reader(handle))


def literals(root: Path, pattern: re.Pattern[str], suffixes: tuple[str, ...]) -> set[str]:
	found = set()
	for path in root.rglob("*"):
		if path.suffix not in suffixes or "tests" in path.parts or "node_modules" in path.parts:
			continue
		for match in pattern.finditer(path.read_text(encoding="utf-8")):
			text = next(group for group in match.groups() if group is not None)
			found.add(text.replace("\\'", "'").replace('\\"', '"'))
	return found


# Strings kept in constants and shown through __(variable): the key names those objects use.
LABEL_KEY = re.compile(
	r"""\b(?:label|title|text|description|hint|placeholder|heading|caption)\s*:\s*(?:'((?:[^'\\]|\\.)*)'|"((?:[^"\\]|\\.)*)")"""
)
NOT_TRANSLATED = {"Aref Ruqaa", "Dancing Script", "Great Vibes", "English", "Inter"}


class TestArabicCsv(UnitTestCase):
	def test_every_row_has_a_source_and_a_translation(self):
		for row in rows():
			self.assertEqual(len(row), 2, row)
			self.assertTrue(row[0].strip() and row[1].strip(), row)

	def test_no_source_is_listed_twice(self):
		sources = [row[0] for row in rows()]
		self.assertEqual(len(sources), len(set(sources)))

	def test_placeholders_survive_translation(self):
		for source, translation in rows():
			self.assertEqual(
				sorted(PLACEHOLDER.findall(source)), sorted(PLACEHOLDER.findall(translation)), source
			)

	def test_no_em_dashes(self):
		self.assertFalse([row for row in rows() if chr(0x2014) in row[1]])

	def test_translations_contain_arabic_unless_they_are_identifiers(self):
		for source, translation in rows():
			if not re.search(r"[؀-ۿ]", translation):
				self.assertRegex(translation, r"^[A-Za-z0-9_\-/.(){}\[\]#:, ]+$", source)


class TestCoverage(UnitTestCase):
	def known(self) -> set[str]:
		core = frappe.translate.get_translations_from_apps("ar", ["frappe"])
		return {row[0] for row in rows()} | set(core)

	def test_every_frontend_string_is_translated(self):
		missing = literals(FRONTEND, JS_STRING, (".vue", ".ts")) - self.known()
		self.assertEqual(sorted(missing), [])

	def test_labels_kept_in_constants_are_translated(self):
		labels = literals(FRONTEND, LABEL_KEY, (".vue", ".ts")) - NOT_TRANSLATED
		words = {
			text
			for text in labels
			if re.search(r"[A-Za-z]{3}", text) and not text.startswith(("lucide-", "#"))
		}
		self.assertEqual(sorted(words - self.known()), [])

	def test_every_desk_script_string_is_translated(self):
		bundle = APP / "public" / "js"
		missing = literals(bundle, JS_STRING, (".js",)) - self.known()
		self.assertEqual(sorted(missing), [])

	def test_every_python_string_is_translated(self):
		missing = {
			text for text in literals(APP, PY_STRING, (".py",)) if re.search(r"[A-Za-z]{3}", text)
		} - self.known()
		self.assertEqual(sorted(missing), [])
