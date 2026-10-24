"""The import graph follows the layer rules in docs/ARCHITECTURE.md and CLAUDE.md."""

import ast
from pathlib import Path

from frappe.tests import UnitTestCase

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PACKAGE = PACKAGE_ROOT.name

# Layers each layer may import from inside the app. "doctype" is the module folder that holds the
# DocType controllers. "crypto.pkcs12" is the one crypto module that controllers may import.
SHARED = {"utils", "exceptions", "compat"}
ALLOWED_IMPORTS: dict[str, set[str]] = {
	"api": {"api", "services"} | SHARED,
	"services": {"services", "pdf", "crypto", "doctype"} | SHARED,
	"pdf": {"pdf", "crypto"},
	"crypto": {"crypto"},
	"erpnext": {"erpnext", "services"} | SHARED,
	"jobs": {"services"} | SHARED,
	"doctype": {"doctype", "crypto.pkcs12"} | SHARED,
	# utils/, exceptions.py and compat.py form one shared tier and may use each other.
	"utils": SHARED,
	"exceptions": set(),
	"compat": set(),
	"www": {"services"} | SHARED,
	"commands": {"services"} | SHARED,
	"jinja": SHARED,
	"patches": {"services", "doctype"} | SHARED,
	"hooks": set(),
	"config": set(),
	"templates": set(),
	"package": set(),
	"tests": set(),
}
# pdf/ is pure; only these two stages need frappe.
PDF_MODULES_ALLOWED_FRAPPE = {"pdf.source", "pdf.certificate"}


def module_name(path: Path) -> str:
	relative = path.relative_to(PACKAGE_ROOT).with_suffix("")
	parts = [PACKAGE, *relative.parts]
	if parts[-1] == "__init__":
		parts.pop()
	return ".".join(parts)


def layer_of(module: str) -> str:
	parts = module.split(".")
	if len(parts) == 1:
		return "package"
	head = parts[1]
	if head == PACKAGE:
		return "doctype"
	if head == "crypto" and parts[2:3] == ["pkcs12"]:
		return "crypto.pkcs12"
	return head if head in ALLOWED_IMPORTS else "unknown"


def module_exists(module: str) -> bool:
	path = PACKAGE_ROOT.joinpath(*module.split(".")[1:])
	return path.with_suffix(".py").exists() or (path / "__init__.py").exists()


def imported_modules(source: str, module: str, is_package: bool) -> list[str]:
	"""Every module imported anywhere in `source`, including guarded imports inside functions."""
	package_parts = module.split(".") if is_package else module.split(".")[:-1]
	found: list[str] = []
	for node in ast.walk(ast.parse(source)):
		if isinstance(node, ast.Import):
			found.extend(alias.name for alias in node.names)
		elif isinstance(node, ast.ImportFrom):
			base = node.module or ""
			if node.level:
				prefix = package_parts[: len(package_parts) - node.level + 1]
				base = ".".join([*prefix, base] if base else prefix)
			for alias in node.names:
				candidate = f"{base}.{alias.name}"
				is_submodule = base.split(".")[0] == PACKAGE and module_exists(candidate)
				found.append(candidate if is_submodule else base)
	return found


def violations(path: Path, source: str) -> list[str]:
	module = module_name(path)
	layer = layer_of(module)
	if layer == "unknown":
		return [f"{module}: not in a known layer; add it to ALLOWED_IMPORTS"]

	in_erpnext_tests = module.startswith(f"{PACKAGE}.tests.erpnext")
	problems = []
	for imported in imported_modules(source, module, path.name == "__init__.py"):
		top = imported.split(".")[0]
		short = imported.removeprefix(f"{PACKAGE}.")
		if top == "erpnext" and layer != "erpnext" and not in_erpnext_tests:
			problems.append(f"{module}: imports {imported}; core code never imports erpnext (D4)")
		elif top == "frappe" and layer == "crypto":
			problems.append(f"{module}: imports {imported}; crypto/ never touches frappe")
		elif (
			top == "frappe"
			and layer == "pdf"
			and module.removeprefix(f"{PACKAGE}.") not in (PDF_MODULES_ALLOWED_FRAPPE)
		):
			problems.append(f"{module}: imports {imported}; pdf/ is pure ({short})")
		elif top == PACKAGE and layer != "tests":
			target = layer_of(imported)
			allowed = ALLOWED_IMPORTS.get(layer, set())
			if target == "crypto.pkcs12" and "crypto" in allowed:
				continue
			if target not in allowed:
				problems.append(f"{module}: {layer}/ may not import {target} ({imported})")
	return problems


class TestLayerRules(UnitTestCase):
	def test_app_follows_layer_rules(self):
		problems = []
		for path in sorted(PACKAGE_ROOT.rglob("*.py")):
			if "node_modules" in path.parts:
				continue
			problems.extend(violations(path, path.read_text()))
		self.assertEqual(problems, [], "\n".join(problems))

	def test_checker_flags_known_violations(self):
		def check(relative: str, source: str) -> list[str]:
			return violations(PACKAGE_ROOT / relative, source)

		self.assertTrue(check("services/x.py", "import erpnext"))
		self.assertTrue(check("services/x.py", "def f():\n    from erpnext.stock import utils"))
		self.assertTrue(check("api/x.py", "from frappe_sign.pdf import overlay"))
		self.assertTrue(check("api/x.py", "from ..jobs import seal"))
		self.assertTrue(check("pdf/overlay.py", "import frappe"))
		self.assertTrue(check("pdf/overlay.py", "from frappe_sign import exceptions"))
		self.assertTrue(check("crypto/signer.py", "import frappe"))
		self.assertTrue(
			check(
				"frappe_sign/doctype/sign_envelope/sign_envelope.py",
				"from frappe_sign.services import envelope",
			)
		)
		self.assertTrue(
			check(
				"frappe_sign/doctype/sign_certificate/sign_certificate.py",
				"from frappe_sign.crypto import signer",
			)
		)
		self.assertTrue(check("utils/x.py", "from frappe_sign.services import audit"))
		self.assertTrue(check("newlayer/x.py", ""))

	def test_checker_allows_permitted_imports(self):
		def check(relative: str, source: str) -> list[str]:
			return violations(PACKAGE_ROOT / relative, source)

		self.assertEqual(check("pdf/source.py", "import frappe"), [])
		self.assertEqual(check("pdf/seal.py", "from frappe_sign.crypto.signer import Signer"), [])
		self.assertEqual(check("api/x.py", "from frappe_sign.services import envelope"), [])
		self.assertEqual(check("api/x.py", "from frappe_sign import exceptions"), [])
		self.assertEqual(check("services/x.py", "from . import audit"), [])
		self.assertEqual(
			check(
				"frappe_sign/doctype/sign_certificate/sign_certificate.py",
				"from frappe_sign.crypto import pkcs12",
			),
			[],
		)
		self.assertEqual(check("erpnext/setup.py", "import erpnext"), [])
		self.assertEqual(check("tests/erpnext/test_x.py", "import erpnext"), [])
