"""The send job places fields from sign_field() anchors in the rendered Print Format (P2.2)."""

import json
import unittest
from unittest.mock import patch

import frappe

from frappe_sign.services import envelope as envelope_service
from frappe_sign.services import template as template_service
from frappe_sign.tests.base import SignTestCase
from frappe_sign.tests.factories import make_user
from frappe_sign.tests.printing import make_print_format
from frappe_sign.tests.signing_helpers import CUSTOMER, send_now
from frappe_sign.tests.unit.test_anchors import A4, marker_pdf

HTML = """<p>{{ doc.description }}</p>
<p>{{ sign_field("signature", role="Customer", width=60, height=20) }}</p>
<p>{{ sign_field("date_signed", role="Customer") }}</p>
<p>{{ sign_field("signature", role="Witness") }}</p>"""
# Where the stub generator draws each marker (points from the top-left).
POSITIONS = {
	"[[fs:Customer:signature:1]]": (100, 300),
	"[[fs:Customer:date_signed:1]]": (100, 400),
	"[[fs:Witness:signature:1]]": (100, 500),
}


def anchor_field(**overrides) -> dict:
	return {
		"field_key": "customer_signature",
		"role_label": "Customer",
		"field_type": "Signature",
		"page": 0,
		"anchor_tag": "[[fs:Customer:signature:1]]",
		"required": 1,
		**overrides,
	}


class TestAnchoredSend(SignTestCase):
	def setUp(self):
		super().setUp()
		self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Anchored"}).insert()
		self.print_format = make_print_format("ToDo", HTML, "chrome")

	def send(self, fields: list[dict], drawn: list[str] | None = None, sender: str = "Administrator"):
		template = self.publish(fields)
		with self.as_user(sender):
			if sender != "Administrator":
				self.todo = frappe.get_doc({"doctype": "ToDo", "description": "Mine"}).insert()
			draft = envelope_service.create_draft(
				{
					"template_version": template,
					"reference_doctype": "ToDo",
					"reference_name": self.todo.name,
					"recipients": [CUSTOMER],
				}
			)
			markers = [(tag, *POSITIONS[tag]) for tag in (drawn if drawn is not None else POSITIONS)]
			with patch("frappe.utils.pdf.get_chrome_pdf", return_value=marker_pdf(markers)):
				send_now(draft.name)
		return frappe.get_doc("Sign Envelope", draft.name)

	def publish(self, fields: list[dict]) -> str:
		template = template_service.create_template(
			{
				"title": "Anchored",
				"source_type": "Print Format",
				"reference_doctype": "ToDo",
				"print_format": self.print_format.name,
				"roles": [{"role_label": "Customer", "kind": "Signer", "signer_source": "Ask at Send"}],
				"fields": fields,
			}
		)
		return template_service.publish(template.name).name

	def test_fields_take_the_anchor_rects(self):
		doc = self.send([anchor_field()])
		fields = {field.field_key: field for field in doc.fields}
		signature = fields["customer_signature"]
		self.assertEqual(signature.page, 1)
		self.assertAlmostEqual(signature.x, 100 / A4[0], 3)
		self.assertAlmostEqual(signature.y, 300 / A4[1], 3)
		self.assertAlmostEqual(signature.w, 60 * 72 / 25.4 / A4[0], 3)

	def test_anchor_without_a_field_becomes_one_for_its_signer(self):
		doc = self.send([anchor_field()])
		fields = {field.field_key: field for field in doc.fields}
		date = fields["customer_date_signed_1"]
		self.assertEqual((date.field_type, date.required, date.page), ("Date Signed", 0, 1))
		self.assertEqual(date.recipient_row, doc.recipients[0].name)
		sent = frappe.get_all("Sign Event", filters={"envelope": doc.name, "event": "Sent"}, pluck="payload")[
			0
		]
		payload = json.loads(sent)
		self.assertEqual(payload["anchors"], 3)
		self.assertEqual(payload["unused_anchors"], ["[[fs:Witness:signature:1]]"])

	def test_a_sign_user_sender_gets_the_anchor_fields(self):
		make_user("sign-user-anchors@example.com", "Sign User")
		doc = self.send([anchor_field()], sender="sign-user-anchors@example.com")
		self.assertEqual(doc.status, "Sent")
		self.assertIn("customer_date_signed_1", {field.field_key for field in doc.fields})

	def test_missing_required_anchor_fails_the_send(self):
		with self.assertRaises(envelope_service.SendFailed) as raised:
			self.send([anchor_field()], drawn=["[[fs:Customer:date_signed:1]]"])
		self.assertIn("customer_signature", str(raised.exception))

	def test_missing_optional_anchor_drops_the_field(self):
		doc = self.send(
			[
				anchor_field(),
				anchor_field(
					field_key="initials",
					field_type="Initials",
					required=0,
					anchor_tag="[[fs:Customer:initials:1]]",
				),
			]
		)
		self.assertNotIn("initials", {field.field_key for field in doc.fields})


if __name__ == "__main__":
	unittest.main()
