"""Staff API permissions (P1.13): Sign User vs Sign Manager, and the public verify API."""

import base64
import io

import frappe
from pypdf import PdfReader

from frappe_sign.api import public, staff
from frappe_sign.exceptions import InvalidTransition
from frappe_sign.jobs import seal as seal_job
from frappe_sign.services import envelope as envelope_service
from frappe_sign.tests.factories import fixture_pdf, make_profile, make_user, test_company
from frappe_sign.tests.integration.test_sealing import no_commits, offline_seal
from frappe_sign.tests.integration.test_signing_service import SigningCase
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, send_now
from frappe_sign.utils.files import read_file

ALICE = "alice.sender@example.com"
BOB = "bob.other@example.com"
MANAGER = "mona.manager@example.com"
RECIPIENT = "ahmed@example.com"


class PermissionCase(SigningCase):
	def setUp(self):
		super().setUp()
		make_user(ALICE, "Sign User")
		make_user(BOB, "Sign User")
		make_user(MANAGER, "Sign Manager")
		make_user(RECIPIENT, "Sign User")

	def alice_envelope(self) -> str:
		"""A template published by the manager, then sent by Alice."""
		self.sent()
		frappe.db.set_value("Sign Envelope", self.name, {"sender": ALICE, "owner": ALICE})
		return self.name


class TestEnvelopeVisibility(PermissionCase):
	def test_events_say_how_long_ago_they_happened(self):
		name = self.alice_envelope()
		with self.as_user(ALICE):
			events = staff.get_envelope(name)["events"]
		self.assertTrue(events)
		self.assertTrue(all(0 <= event["ago_seconds"] < 300 for event in events))

	def test_sender_recipient_other_and_manager(self):
		name = self.alice_envelope()
		with self.as_user(ALICE):
			self.assertEqual(staff.get_envelope(name)["envelope"]["name"], name)
			self.assertIn(name, frappe.get_list("Sign Envelope", pluck="name"))
		with self.as_user(RECIPIENT):
			self.assertIn(name, frappe.get_list("Sign Envelope", pluck="name"))
			self.assertFalse(staff.get_envelope(name)["can_write"])
			self.assertRaises(frappe.PermissionError, staff.void_envelope, name, "not mine")
		with self.as_user(BOB):
			self.assertNotIn(name, frappe.get_list("Sign Envelope", pluck="name"))
			self.assertRaises(frappe.PermissionError, staff.get_envelope, name)
			self.assertRaises(frappe.PermissionError, staff.remind, name)
			self.assertRaises(frappe.PermissionError, staff.download, name, "original")
		with self.as_user(MANAGER):
			self.assertIn(name, frappe.get_list("Sign Envelope", pluck="name"))
			self.assertTrue(staff.get_envelope(name)["can_write"])

	def test_sharing_grants_access(self):
		name = self.alice_envelope()
		frappe.share.add_docshare("Sign Envelope", name, BOB, read=1, flags={"ignore_share_permission": True})
		with self.as_user(BOB):
			self.assertEqual(staff.get_envelope(name)["envelope"]["name"], name)
			self.assertRaises(frappe.PermissionError, staff.void_envelope, name, "read only share")

	def test_sender_can_void_and_remind(self):
		name = self.alice_envelope()
		with self.as_user(ALICE), self.capture_enqueue():
			self.assertEqual(staff.remind(name)["reminded"], 1)
			staff.void_envelope(name, "Changed my mind")
		self.assertEqual(frappe.db.get_value("Sign Envelope", name, "status"), "Voided")

	def test_audit_timeline_is_returned_with_the_envelope(self):
		name = self.alice_envelope()
		with self.as_user(ALICE):
			detail = staff.get_envelope(name)
		self.assertEqual([event["event"] for event in detail["events"]][:3], ["Created", "Sent", "Delivered"])
		self.assertTrue(detail["chain_ok"])
		self.assertNotIn("token_hash", frappe.as_json(detail))


class TestStaffActions(PermissionCase):
	def test_sign_user_cannot_publish_or_retry_seal(self):
		name = self.alice_envelope()
		template = frappe.db.get_value(
			"Sign Template Version",
			frappe.db.get_value("Sign Envelope", name, "template_version"),
			"template",
		)
		with self.as_user(ALICE):
			self.assertRaises(frappe.PermissionError, staff.publish_template, template)
			self.assertRaises(frappe.PermissionError, staff.retry_seal, name)
		with self.as_user(MANAGER):
			self.assertRaises(InvalidTransition, staff.retry_seal, name)
			self.assertEqual(staff.publish_template(template)["version_no"], 2)

	def test_send_wizard_flow_for_a_sign_user(self):
		with self.as_user(ALICE):
			staged = staff.upload_pdf(
				file_name="contract.pdf", content=base64.b64encode(fixture_pdf()).decode()
			)
			self.assertEqual(staged["metrics"][0]["page"], 1)
			payload = {
				"title": "Contract",
				"source_file": staged["file_url"],
				"signing_order": "Sequential",
				"recipients": [{"role_label": "Customer", "full_name": "Ahmed Khan", "email": RECIPIENT}],
				"fields": [
					{
						"field_key": "sig",
						"role_label": "Customer",
						"field_type": "Signature",
						"page": 1,
						"x": 0.1,
						"y": 0.8,
						"w": 0.3,
						"h": 0.06,
					}
				],
			}
			name = staff.create_envelope(frappe.as_json(payload))["name"]
			with self.capture_enqueue() as calls:
				self.assertEqual(staff.send_envelope(name)["send_state"], "Queued")
			self.assertEqual(calls[0]["method"], "frappe_sign.jobs.render.run")
		file = frappe.get_doc("File", {"file_url": staged["file_url"]})
		self.assertEqual(
			(file.attached_to_doctype, file.attached_to_name, file.is_private), ("Sign Envelope", name, 1)
		)
		with self.as_user(BOB):
			bob = staff.upload_pdf(file_name="x.pdf", content=base64.b64encode(fixture_pdf()).decode())
		with self.as_user(ALICE):
			stolen = {**payload, "source_file": bob["file_url"]}
			self.assertRaises(frappe.PermissionError, staff.create_envelope, frappe.as_json(stolen))

	def test_my_signing_link_for_a_company_signer(self):
		draft = make_draft(
			recipients=[
				{"role_label": "Customer", "full_name": "Alice", "email": ALICE},
				{"role_label": "Company", "full_name": "Mona", "email": MANAGER},
			]
		)
		with capture_tokens() as box:
			send_now(draft.name)
		with self.as_user(ALICE):
			url = staff.my_signing_link(draft.name)["url"]
		alice_row = next(
			r for r in frappe.get_doc("Sign Envelope", draft.name).recipients if r.email == ALICE
		)
		self.assertTrue(url.endswith(f"/s/{box[alice_row.name]}"), "the same link as in the email")
		with self.as_user(MANAGER):
			self.assertRaises(InvalidTransition, staff.my_signing_link, draft.name)

	def test_dashboard_counts(self):
		self.alice_envelope()
		with self.as_user(ALICE):
			cards = staff.get_dashboard()
		self.assertEqual([row["name"] for row in cards["waiting"]], [self.name])
		self.assertEqual(cards["month"]["waiting"], 1)
		with self.as_user(RECIPIENT):
			cards = staff.get_dashboard()
		self.assertEqual([row["name"] for row in cards["to_sign"]], [self.name])
		self.assertEqual(cards["waiting"], [], "the recipient did not send it")


class TestDownloadsAndVerify(PermissionCase):
	def completed(self) -> str:
		make_profile(test_company())
		self.sent(company=test_company())
		frappe.db.set_value(
			"Sign Envelope", self.name, {"company": test_company(), "sender": ALICE, "owner": ALICE}
		)
		self.sign("Customer")
		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		return self.name

	def test_downloads(self):
		name = self.completed()
		with self.as_user(ALICE):
			signed = staff.download(name, "signed")
			certificate = staff.download(name, "certificate")
			self.assertRaises(InvalidTransition, staff.download, name, "receipt")
		self.assertEqual(
			signed.get_data(), read_file(frappe.db.get_value("Sign Envelope", name, "signed_file"))
		)
		self.assertEqual(signed.headers["Cache-Control"], "no-store")
		pages = PdfReader(io.BytesIO(certificate.get_data())).pages
		self.assertIn("Certificate of Completion", pages[0].extract_text())
		self.assertIn("Downloaded", frappe.get_all("Sign Event", filters={"envelope": name}, pluck="event"))

	def test_public_verify_by_file_and_by_id(self):
		name = self.completed()
		sealed = read_file(frappe.db.get_value("Sign Envelope", name, "signed_file"))
		with self.as_user("Guest"):
			by_file = public.verify(file=base64.b64encode(sealed).decode())
			by_id = public.verify(envelope=name)
			tampered = public.verify(
				file=base64.b64encode(sealed.replace(b"595.2756", b"595.2757", 1)).decode()
			)
		self.assertTrue(by_file["found"] and by_file["matches"])
		self.assertEqual([s["name"] for s in by_file["signers"]], ["Ahmed Khan", "Fatima Ali"])
		self.assertTrue(by_file["seal"]["intact"] and by_file["seal"]["valid"])
		self.assertTrue(by_file["seal"]["trusted"], "the profile's own root is trusted")
		self.assertTrue(by_file["seal"]["timestamp_valid"])
		self.assertEqual((by_id["status"], by_id["sealed"]), ("Completed", True))
		self.assertNotIn("signers", by_id, "an envelope ID alone does not reveal who signed")
		self.assertFalse(tampered["found"])
		self.assertFalse(tampered["seal"]["intact"])

	def test_unknown_envelope_and_unsigned_file(self):
		with self.as_user("Guest"):
			self.assertEqual(public.verify(envelope="SIGN-2026-99999"), {"found": False})
			result = public.verify(file=base64.b64encode(fixture_pdf()).decode())
		self.assertFalse(result["found"])
		self.assertFalse(result["seal"]["signed"])
