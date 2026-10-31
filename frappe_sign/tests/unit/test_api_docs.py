"""docs/API.md is generated from the whitelisted functions (P3.9) and must be current."""

import subprocess
import sys
from pathlib import Path

from frappe.tests import UnitTestCase

ROOT = Path(__file__).resolve().parents[3]


class TestApiDocs(UnitTestCase):
	def test_the_api_reference_is_up_to_date(self):
		result = subprocess.run(
			[sys.executable, str(ROOT / "scripts" / "make_api_docs.py"), "--check"], capture_output=True
		)
		self.assertEqual(result.returncode, 0, "Run: python3 scripts/make_api_docs.py")

	def test_every_whitelisted_function_is_listed(self):
		text = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")
		for name in ("get_dashboard", "open", "finish", "verify", "download", "get_health", "bulk_send"):
			self.assertIn(f"### `{name}`", text)
