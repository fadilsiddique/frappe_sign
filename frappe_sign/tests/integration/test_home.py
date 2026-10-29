"""Home data: what waits for the user, what the user waits for, and the month's figures (U.3)."""

import frappe
from frappe.utils import add_days, now_datetime

from frappe_sign.api import staff
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.signing_helpers import COMPANY, CUSTOMER, make_draft, publish_template, send_now

ADMIN = {**CUSTOMER, "full_name": "Administrator", "email": "admin@example.com"}


class TestHome(SignTestCase):
	def setUp(self):
		super().setUp()
		self.refuse_commits()
		frappe.db.delete("Sign Envelope")

	def sent(self, recipients=None, signing_order="Sequential", **payload) -> str:
		draft = make_draft(publish_template(signing_order), recipients=recipients, **payload)
		send_now(draft.name)
		return draft.name

	def row(self, name: str, role: str) -> str:
		return frappe.db.get_value("Sign Envelope Recipient", {"parent": name, "role_label": role})

	def waiting(self, name: str) -> dict:
		return next(row for row in staff.get_dashboard()["waiting"] if row["name"] == name)

	def test_what_waits_for_my_signature(self):
		name = self.sent([ADMIN, COMPANY], title="Lease for Unit 4B")
		(row,) = staff.get_dashboard()["to_sign"]
		self.assertEqual(row["name"], name)
		self.assertEqual(row["title"], "Lease for Unit 4B")
		self.assertEqual(row["sender_name"], "Administrator")
		self.assertEqual(row["kind"], "Signer")
		self.assertGreaterEqual(row["age_seconds"], 0)

	def test_not_yet_my_turn_is_not_waiting_for_me(self):
		self.sent([CUSTOMER, {**ADMIN, "role_label": "Company"}])
		self.assertEqual(staff.get_dashboard()["to_sign"], [])

	def test_waiting_on_someone_outside_or_on_my_team(self):
		outside = self.sent([CUSTOMER, COMPANY])
		team = self.sent([ADMIN, COMPANY])
		self.assertEqual(self.waiting(outside)["group"], "outside")
		self.assertEqual([p["full_name"] for p in self.waiting(outside)["next"]], ["Ahmed Khan"])
		self.assertEqual(self.waiting(team)["group"], "team")
		self.assertEqual([p["full_name"] for p in self.waiting(team)["next"]], ["Administrator"])

	def test_everyone_is_next_when_signing_at_once(self):
		name = self.sent([CUSTOMER, COMPANY], signing_order="Parallel")
		self.assertEqual([p["full_name"] for p in self.waiting(name)["next"]], ["Ahmed Khan", "Fatima Ali"])

	def test_people_in_order_with_progress(self):
		name = self.sent([CUSTOMER, COMPANY])
		frappe.db.set_value("Sign Envelope Recipient", self.row(name, "Customer"), "status", "Signed")
		frappe.db.set_value("Sign Envelope Recipient", self.row(name, "Company"), "status", "Sent")
		row = self.waiting(name)
		self.assertEqual(
			[(p["full_name"], p["status"], p["next"]) for p in row["people"]],
			[("Ahmed Khan", "Signed", False), ("Fatima Ali", "Sent", True)],
		)
		self.assertEqual(
			[p["name"] for p in row["people"]], [self.row(name, "Customer"), self.row(name, "Company")]
		)
		self.assertEqual((row["signed"], row["total"]), (1, 2))

	def test_opened_shows_how_long_ago(self):
		name = self.sent([CUSTOMER, COMPANY])
		frappe.db.set_value(
			"Sign Envelope Recipient",
			self.row(name, "Customer"),
			{"status": "Viewed", "viewed_on": add_days(now_datetime(), -1)},
		)
		(person,) = self.waiting(name)["next"]
		self.assertEqual(person["status"], "Viewed")
		self.assertGreaterEqual(person["viewed_seconds"], 86_000)

	def test_expiring_soon(self):
		later = self.sent([CUSTOMER, COMPANY])
		soon = self.sent([CUSTOMER, COMPANY])
		frappe.db.set_value("Sign Envelope", soon, "expires_on", add_days(now_datetime(), 1))
		self.assertFalse(self.waiting(later)["expiring_soon"])
		self.assertTrue(self.waiting(soon)["expiring_soon"])
		self.assertEqual(self.waiting(soon)["expires_on"], str(add_days(now_datetime(), 1).date()))

	def test_month_figures(self):
		self.sent([CUSTOMER, COMPANY])
		done = self.sent([CUSTOMER, COMPANY])
		declined = self.sent([CUSTOMER, COMPANY])
		frappe.db.set_value("Sign Envelope", done, {"status": "Completed", "completed_on": now_datetime()})
		frappe.db.set_value("Sign Envelope", declined, "status", "Declined")
		self.assertEqual(staff.get_dashboard()["month"], {"completed": 1, "waiting": 1, "declined": 1})
