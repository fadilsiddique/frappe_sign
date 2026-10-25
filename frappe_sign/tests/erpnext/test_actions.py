"""Post-sign actions (P2.7, DESIGN 4.6): a signed Quotation becomes a draft Sales Order, run as the
sender; a failing action is recorded and never undoes the signature."""

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_sign.jobs import actions as actions_job
from frappe_sign.services import actions
from frappe_sign.tests.erpnext.helpers import ERPNextTestCase, make_quotation
from frappe_sign.tests.erpnext.quotation import publish_quotation_template, signed_quotation
from frappe_sign.tests.factories import make_user
from frappe_sign.tests.integration.test_sealing import no_commits

MAKE_SALES_ORDER = "erpnext.selling.doctype.quotation.quotation.make_sales_order"
# The pilot's config: ERPNext's mapper leaves the Delivery Date empty, and Sales Order needs one.
SALES_ORDER_CONFIG = {"method": MAKE_SALES_ORDER, "save": 1, "values": {"delivery_date": "today+7"}}


def action_events(envelope: str) -> list[dict]:
	payloads = frappe.get_all(
		"Sign Event",
		filters={"envelope": envelope, "event": actions.EVENT},
		pluck="payload",
		order_by="seq asc",
	)
	return [json.loads(payload) for payload in payloads]


class TestPostSignActions(ERPNextTestCase):
	def setUp(self):
		super().setUp()
		self.quotation = make_quotation(items=3, submit=True)

	def complete(self, action: str, config: dict | None = None) -> str:
		template = publish_quotation_template(
			customer_only=True, post_sign_action=action, post_sign_config=json.dumps(config or {})
		)
		return signed_quotation(self.quotation.name, template)

	def run_job(self, envelope: str) -> None:
		with self.capture_enqueue() as calls:
			actions.queue_post_sign(envelope)
		self.assertEqual([call["method"] for call in calls], [actions.JOB])
		with no_commits(), patch("frappe.enqueue"):
			actions_job.run(envelope)

	def sales_orders(self) -> list:
		parents = frappe.get_all(
			"Sales Order Item",
			filters={"prevdoc_docname": self.quotation.name},
			pluck="parent",
			distinct=True,
		)
		return frappe.get_all(
			"Sales Order", filters={"name": ["in", parents or [""]]}, fields=["name", "docstatus", "owner"]
		)

	def test_quotation_becomes_a_draft_sales_order(self):
		envelope = self.complete("Create Mapped Document", SALES_ORDER_CONFIG)
		self.assertEqual(frappe.db.get_value("Sign Envelope", envelope, "status"), "Completed")
		self.run_job(envelope)
		self.assertEqual(action_events(envelope)[0].get("error"), None)
		[order] = self.sales_orders()
		self.assertEqual(order.docstatus, 0)
		self.assertEqual(order.owner, "Administrator")  # the sender
		[event] = action_events(envelope)
		self.assertEqual(
			(event["action"], event["status"], event["name"]), ("Create Mapped Document", "ok", order.name)
		)

	def test_runs_as_the_sender_with_their_permissions(self):
		make_user("no-sales@example.com", "Sign User")
		envelope = self.complete("Create Mapped Document", SALES_ORDER_CONFIG)
		frappe.db.set_value("Sign Envelope", envelope, "sender", "no-sales@example.com")
		self.run_job(envelope)
		self.assertEqual(self.sales_orders(), [])
		[event] = action_events(envelope)
		self.assertEqual(event["status"], "failed")
		self.assertEqual(frappe.db.get_value("Sign Envelope", envelope, "status"), "Completed")

	def test_failure_is_logged_and_the_sender_told(self):
		envelope = self.complete(
			"Create Mapped Document", {"method": "frappe_sign.services.actions.registry"}
		)
		self.run_job(envelope)
		[event] = action_events(envelope)
		self.assertEqual(event["status"], "failed")
		self.assertIn("not whitelisted", event["error"])
		self.assertTrue(
			frappe.db.exists(
				"Error Log", {"method": "Frappe Sign: post-sign action", "reference_name": envelope}
			)
		)
		self.assertTrue(
			frappe.db.exists(
				"Notification Log", {"document_name": envelope, "subject": ["like", "%post-sign action%"]}
			)
		)
		envelope_doc = frappe.get_doc("Sign Envelope", envelope)
		self.assertEqual((envelope_doc.status, envelope_doc.sealing_state), ("Completed", "Sealed"))

	def test_relative_dates_in_config(self):
		self.assertEqual(
			str(actions.resolve_value("today+7")), frappe.utils.add_days(frappe.utils.today(), 7)
		)
		self.assertEqual(str(actions.resolve_value("today")), frappe.utils.today())
		self.assertEqual(actions.resolve_value("Maintenance"), "Maintenance")

	def test_set_field_value(self):
		envelope = self.complete("Set Field Value", {"fieldname": "order_type", "value": "Maintenance"})
		self.quotation.reload()
		self.quotation.db_set("docstatus", 0)  # Set Field Value saves; a draft accepts any field
		self.run_job(envelope)
		self.assertEqual(frappe.db.get_value("Quotation", self.quotation.name, "order_type"), "Maintenance")

	def test_submit(self):
		self.quotation.db_set("docstatus", 0)
		envelope = self.complete("Submit")
		self.run_job(envelope)
		self.assertEqual(frappe.db.get_value("Quotation", self.quotation.name, "docstatus"), 1)

	def test_none_queues_nothing(self):
		envelope = self.complete("None")
		with self.capture_enqueue() as calls:
			actions.queue_post_sign(envelope)
		self.assertEqual(calls, [])
		self.assertIsNone(actions.run_post_sign(envelope))

	def test_registered_actions_from_other_apps(self):
		def stamp(envelope, doc, config):
			return {"stamped": doc.name, "with": config.get("label")}

		hooks = {"frappe_sign_post_sign_actions": {"Stamp": ["some_app.stamp"]}}
		with patch("frappe.get_hooks", side_effect=lambda name, default=None, **kw: hooks.get(name, default)):
			with patch("frappe.get_attr", return_value=stamp):
				registry = actions.registry()
		self.assertIn("Stamp", registry)
		self.assertEqual(
			registry["Stamp"](None, self.quotation, {"label": "x"}),
			{"stamped": self.quotation.name, "with": "x"},
		)


if __name__ == "__main__":
	unittest.main()
