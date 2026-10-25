"""Desk scripts are bundles, so each release gets a new URL.

A plain /assets/frappe_sign/js/... path keeps its URL across releases and Frappe serves it with a
12 hour max-age. Browsers then run the old script against new form scripts: "Create test
certificate" failed with "test_certificate_dialog is not a function" that way, while Playwright,
which starts with an empty cache, passed.
"""

from pathlib import Path

from frappe.tests import UnitTestCase

from frappe_sign import hooks

PUBLIC = Path(hooks.__file__).resolve().parent / "public"


def as_list(value) -> list[str]:
	return [value] if isinstance(value, str) else list(value or [])


class TestDeskAssets(UnitTestCase):
	def test_app_includes_are_bundles_that_exist(self):
		for key in ("app_include_js", "app_include_css"):
			for path in as_list(getattr(hooks, key, None)):
				with self.subTest(hook=key, path=path):
					self.assertTrue(path.endswith((".bundle.js", ".bundle.css")), path)
					self.assertFalse(path.startswith("/assets/"), path)
					self.assertTrue(list(PUBLIC.rglob(path)), f"{path} is not under public/")

	def test_bundle_names_do_not_clash_with_frappe(self):
		# assets.json is keyed by file name: "desk.bundle.js" would resolve to Frappe's own bundle.
		for path in as_list(hooks.app_include_js):
			self.assertTrue(Path(path).name.startswith("frappe_sign"), path)
