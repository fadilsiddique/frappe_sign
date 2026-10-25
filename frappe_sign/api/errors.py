"""Add the stable error `code` (and `data`) of domain errors to the JSON response (DESIGN 8.4)."""

from collections.abc import Callable
from functools import wraps

import frappe

from frappe_sign.exceptions import FrappeSignError


def with_error_code[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
	@wraps(fn)
	def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
		try:
			return fn(*args, **kwargs)
		except FrappeSignError as error:
			frappe.local.response["code"] = error.code
			if error.data:
				frappe.local.response["data"] = error.data
			raise

	return wrapper
