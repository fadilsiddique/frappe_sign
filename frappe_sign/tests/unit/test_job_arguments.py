"""Job entry points take no argument that frappe.enqueue keeps for itself.

frappe.enqueue(method, queue=..., event=..., ...) consumes its own parameters; a job argument with
the same name never reaches the job. `event` did exactly that to jobs.events.run until Gate 2's
end to end run showed every domain event handler failing in a real worker.
"""

import importlib
import inspect
import pkgutil

import frappe
from frappe.tests import UnitTestCase

import frappe_sign.jobs


class TestJobArguments(UnitTestCase):
	def test_no_job_parameter_is_taken_by_enqueue(self):
		reserved = set(inspect.signature(frappe.enqueue).parameters) - {"method", "kwargs"}
		clashes = []
		for module_info in pkgutil.iter_modules(frappe_sign.jobs.__path__):
			module = importlib.import_module(f"frappe_sign.jobs.{module_info.name}")
			for name, function in inspect.getmembers(module, inspect.isfunction):
				if function.__module__ != module.__name__:
					continue
				clashes += [
					f"{module.__name__}.{name}({param})"
					for param in inspect.signature(function).parameters
					if param in reserved
				]
		self.assertEqual(clashes, [])
