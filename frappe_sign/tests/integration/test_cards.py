"""Number cards of the Signatures workspace (P2.10)."""

import unittest

import frappe

from frappe_sign.api import staff
from frappe_sign.tests.integration.test_signing_service import SigningCase


class TestCards(SigningCase):
	def test_cards_count_the_users_envelopes(self):
		self.sent()
		others = staff.card_awaiting_others()
		self.assertEqual(others["value"], 1)
		self.assertEqual(others["route"], ["List", "Sign Envelope"])
		self.assertEqual(others["route_options"]["sender"], "Administrator")
		self.assertEqual(staff.card_completed_this_month()["value"], 0)
		self.assertEqual(staff.card_expiring_soon()["value"], 0)

	def test_awaiting_me_counts_envelopes_waiting_for_my_email(self):
		self.sent()
		self.assertEqual(staff.card_awaiting_me()["value"], 0)
		frappe.db.set_value("User", "Administrator", "email", "ahmed@example.com")
		mine = staff.card_awaiting_me()
		self.assertEqual(mine["value"], 1)
		self.assertEqual(mine["route_options"], {"name": ["in", [self.name]]})

	def test_cards_are_shipped_with_the_workspace(self):
		workspace = frappe.get_doc("Workspace", "Signatures")
		self.assertEqual(len(workspace.number_cards), 4)
		for row in workspace.number_cards:
			method = frappe.db.get_value("Number Card", row.number_card_name, "method")
			self.assertTrue(callable(frappe.get_attr(method)), method)


if __name__ == "__main__":
	unittest.main()
