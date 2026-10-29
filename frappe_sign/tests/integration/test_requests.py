"""The Sent list: tabs, counts, search, filters, paging and who may see what (U.4)."""

import frappe
from frappe.utils import add_days, now_datetime

from frappe_sign.api import staff
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_user
from frappe_sign.tests.signing_helpers import COMPANY, CUSTOMER, make_draft, publish_template, send_now

ADMIN = {**CUSTOMER, "full_name": "Administrator", "email": "admin@example.com"}


class TestRequests(SignTestCase):
	def setUp(self):
		super().setUp()
		self.refuse_commits()
		frappe.db.delete("Sign Envelope")
		self.version = publish_template()

	def make(self, status="Sent", recipients=None, **fields) -> str:
		draft = make_draft(self.version, recipients=recipients or [CUSTOMER, COMPANY], title="Quote A")
		if status != "Draft":
			send_now(draft.name)
		changes = {"status": status, **fields}
		frappe.db.set_value("Sign Envelope", draft.name, changes)
		return draft.name

	def names(self, **filters) -> list[str]:
		return [row["name"] for row in staff.list_requests(**filters)["rows"]]

	def test_tabs_map_to_statuses(self):
		draft = self.make("Draft")
		waiting = self.make("Sent")
		done = self.make("Completed")
		declined = self.make("Declined")
		expired = self.make("Expired")
		self.assertCountEqual(self.names(status="open"), [draft, waiting])
		self.assertEqual(self.names(status="completed"), [done])
		self.assertCountEqual(self.names(status="closed"), [declined, expired])
		self.assertEqual(len(self.names(status="all")), 5)

	def test_counts_follow_the_filters_but_not_the_tab(self):
		self.make("Sent", title="Lease")
		self.make("Completed", title="Lease")
		self.make("Declined", title="Other")
		self.assertEqual(staff.request_counts(), {"open": 1, "completed": 1, "closed": 1, "all": 3})
		self.assertEqual(
			staff.request_counts(search="Lease"), {"open": 1, "completed": 1, "closed": 0, "all": 2}
		)

	def test_search_finds_title_document_and_people(self):
		one = self.make(title="Lease for Unit 4B")
		two = self.make(reference_doctype="User", reference_name="Administrator")
		three = self.make(recipients=[{**CUSTOMER, "full_name": "Omar Farouk"}, COMPANY])
		self.assertEqual(self.names(status="all", search="unit 4b"), [one])
		self.assertEqual(self.names(status="all", search="Administrator"), [two])
		self.assertEqual(self.names(status="all", search="omar"), [three])
		self.assertEqual(len(self.names(status="all", search="fatima@example.com")), 3)
		self.assertEqual(self.names(status="all", search="nobody"), [])

	def test_search_treats_wildcards_as_text(self):
		self.make(title="100% done")
		self.make(title="Something else")
		self.assertEqual(len(self.names(status="all", search="%")), 1)

	def test_document_type_sender_and_date_filters(self):
		doc = self.make(reference_doctype="User", reference_name="Administrator")
		plain = self.make()
		old = self.make(creation=add_days(now_datetime(), -40))
		self.assertEqual(self.names(status="all", reference_doctype="User"), [doc])
		self.assertCountEqual(self.names(status="all", sender="Administrator"), [doc, plain, old])
		self.assertEqual(self.names(status="all", sender="Guest"), [])
		start = str(add_days(now_datetime(), -7).date())
		self.assertCountEqual(self.names(status="all", date_from=start), [doc, plain])
		self.assertEqual(self.names(status="all", date_to=start), [old])

	def test_filter_options_list_what_exists(self):
		self.make(reference_doctype="User", reference_name="Administrator")
		self.make()
		options = staff.request_filter_options()
		self.assertEqual(options["doctypes"], ["User"])
		self.assertEqual(options["senders"], [{"name": "Administrator", "full_name": "Administrator"}])

	def test_paging(self):
		for _ in range(3):
			self.make()
		page = staff.list_requests(status="all", limit=2)
		self.assertEqual((len(page["rows"]), page["has_more"]), (2, True))
		rest = staff.list_requests(status="all", start=2, limit=2)
		self.assertEqual((len(rest["rows"]), rest["has_more"]), (1, False))
		self.assertFalse({r["name"] for r in page["rows"]} & {r["name"] for r in rest["rows"]})

	def test_rows_say_who_is_next_and_whom_to_chase(self):
		outside = self.make(recipients=[CUSTOMER, COMPANY])
		team = self.make(recipients=[ADMIN, COMPANY])
		rows = {row["name"]: row for row in staff.list_requests(status="all")["rows"]}
		self.assertEqual(rows[outside]["group"], "outside")
		self.assertEqual([p["full_name"] for p in rows[outside]["next"]], ["Ahmed Khan"])
		self.assertEqual(rows[team]["group"], "team")
		self.assertEqual((rows[outside]["signed"], rows[outside]["total"]), (0, 2))
		self.assertEqual(rows[outside]["sender_name"], "Administrator")

	def test_closed_requests_are_not_chased(self):
		done = self.make("Completed")
		row = staff.list_requests(status="completed")["rows"][0]
		self.assertEqual(row["name"], done)
		self.assertEqual(row["group"], "done")
		self.assertEqual(row["next"], [])

	def test_a_draft_has_no_people_to_chase_yet(self):
		draft = self.make("Draft")
		row = next(r for r in staff.list_requests(status="open")["rows"] if r["name"] == draft)
		self.assertEqual(row["group"], "draft")
		self.assertIsNone(row["sent_seconds"])

	def test_a_sign_user_sees_only_their_own(self):
		self.make()
		user = make_user("requests-sign-user@example.com", "Sign User")
		with self.as_user(user.name):
			self.assertEqual(self.names(status="all"), [])
			self.assertEqual(staff.request_counts()["all"], 0)
		mine = self.make(recipients=[{**CUSTOMER, "email": user.name}, COMPANY])
		with self.as_user(user.name):
			self.assertEqual(self.names(status="all"), [mine])

	def test_needs_a_sign_role(self):
		user = make_user("requests-no-role@example.com")
		with self.as_user(user.name):
			self.assertRaises(frappe.PermissionError, staff.list_requests)
			self.assertRaises(frappe.PermissionError, staff.request_counts)
