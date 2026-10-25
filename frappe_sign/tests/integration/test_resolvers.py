"""Recipient resolution for template roles, with Frappe DocTypes only (P2.4, DESIGN 4.3)."""

import unittest

import frappe

from frappe_sign.services import resolvers
from frappe_sign.services import template as template_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_profile, make_user, signature_field, test_company


def publish(roles: list[dict], **extra) -> str:
	template = template_service.create_template(
		{
			"title": "Resolver test",
			"source_type": "Print Format",
			"reference_doctype": "ToDo",
			"company": test_company(),
			"roles": roles,
			"fields": [signature_field(role_label=roles[0]["role_label"], page=1)],
			**extra,
		}
	)
	template_service.publish(template.name)
	return template.name


def role(label: str, source: str, **extra) -> dict:
	return {"role_label": label, "kind": "Signer", "signer_source": source, **extra}


class TestResolveRecipients(SignTestCase):
	needs_email_account = False

	def setUp(self):
		super().setUp()
		self.user = make_user("fatima.signatory@example.com", "Sign User")
		self.todo = frappe.get_doc(
			{"doctype": "ToDo", "description": "Resolve me", "allocated_to": self.user.name}
		).insert()

	def test_doc_field_with_a_user_link(self):
		template = publish([role("Owner", "Doc Field", source_field="allocated_to")])
		[row] = resolvers.resolve_recipients(template, "ToDo", self.todo.name)
		self.assertEqual((row["email"], row["resolved"]), ("fatima.signatory@example.com", True))

	def test_doc_field_with_an_email_value(self):
		self.todo.db_set("description", "someone@example.com")
		template = publish([role("Someone", "Doc Field", source_field="description")])
		[row] = resolvers.resolve_recipients(template, "ToDo", self.todo.name)
		self.assertEqual(row["email"], "someone@example.com")

	def test_fixed_user_and_authorised_signatory(self):
		make_profile(authorised_signatory=self.user.name)
		template = publish(
			[
				role("Customer", "Ask at Send"),
				role("Company", "Fixed User"),
				role("Admin", "Fixed User", fixed_user="Administrator"),
			]
		)
		rows = {
			row["role_label"]: row for row in resolvers.resolve_recipients(template, "ToDo", self.todo.name)
		}
		self.assertFalse(rows["Customer"]["resolved"])
		self.assertEqual(rows["Company"]["email"], "fatima.signatory@example.com")
		self.assertEqual(rows["Admin"]["email"], frappe.db.get_value("User", "Administrator", "email"))

	def test_missing_data_is_unresolved(self):
		template = publish(
			[
				role("Owner", "Doc Field", source_field="no_such_field"),
				role("Party", "Party Contact"),
				role("Staff", "Employee"),
			]
		)
		rows = resolvers.resolve_recipients(template, "ToDo", self.todo.name)
		self.assertEqual([row["resolved"] for row in rows], [False, False, False])
		rows = resolvers.resolve_recipients(template, "ToDo", "no-such-todo")
		self.assertEqual(len(rows), 3)

	def test_contact_and_user_resolvers(self):
		contact = frappe.get_doc(
			{
				"doctype": "Contact",
				"first_name": "Ahmed",
				"last_name": "Khan",
				"email_ids": [{"email_id": "ahmed@example.com", "is_primary": 1}],
				"phone_nos": [{"phone": "+971500000001", "is_primary_mobile_no": 1}],
			}
		).insert()
		[found] = resolvers.suggest("Contact", contact.name)
		self.assertEqual(
			(found["full_name"], found["email"], found["mobile"]),
			("Ahmed Khan", "ahmed@example.com", "+971500000001"),
		)
		[user] = resolvers.suggest("User", self.user.name)
		self.assertEqual(user["email"], "fatima.signatory@example.com")

	def test_invalid_emails_are_dropped(self):
		self.assertIsNone(resolvers.clean({"email": "not an email"})["email"])

	def test_template_must_be_published(self):
		template = template_service.create_template(
			{
				"title": "Draft",
				"source_type": "Print Format",
				"reference_doctype": "ToDo",
				"roles": [role("A", "Ask at Send")],
			}
		)
		with self.assertRaises(frappe.ValidationError):
			resolvers.resolve_recipients(template.name, "ToDo", self.todo.name)


if __name__ == "__main__":
	unittest.main()
