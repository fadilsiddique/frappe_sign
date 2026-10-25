"""Link tokens derived from the site key (D10)."""

import re

from frappe.tests import UnitTestCase

from frappe_sign.utils.hashing import derive_token, sha256_hex

KEY = "test-encryption-key"


class TestDeriveToken(UnitTestCase):
	def test_same_inputs_give_the_same_link(self):
		self.assertEqual(derive_token(KEY, "row1", 1), derive_token(KEY, "row1", 1))

	def test_row_version_and_key_all_change_the_link(self):
		base = derive_token(KEY, "row1", 1)
		for other in (
			derive_token(KEY, "row2", 1),
			derive_token(KEY, "row1", 2),
			derive_token("other-key", "row1", 1),
		):
			self.assertNotEqual(other, base)

	def test_shape_matches_a_random_token(self):
		token = derive_token(KEY, "row1", 1)
		self.assertRegex(token, r"^[A-Za-z0-9_-]{43}$")
		self.assertTrue(re.fullmatch(r"[0-9a-f]{64}", sha256_hex(token)))
