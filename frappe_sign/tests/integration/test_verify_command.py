"""bench frappe-sign verify (P1.18): OK on a good envelope, the first bad event on a tampered one."""

import os

import frappe
from click.testing import CliRunner

from frappe_sign import commands
from frappe_sign.jobs import seal as seal_job
from frappe_sign.tests.factories import make_profile
from frappe_sign.tests.integration.test_sealing import COMPANY, no_commits, offline_seal
from frappe_sign.tests.integration.test_signing_service import SigningCase


class TestVerifyCommand(SigningCase):
	def completed(self) -> str:
		make_profile(COMPANY)
		self.sent(company=COMPANY)
		frappe.db.set_value("Sign Envelope", self.name, "company", COMPANY)
		self.sign("Customer")
		self.sign("Company")
		with offline_seal(), no_commits(), self.capture_enqueue():
			seal_job.run(self.name)
		return self.name

	def test_good_envelope_is_ok(self):
		name = self.completed()
		code, lines = commands.run_verify(name)
		self.assertEqual(code, 0, lines)
		self.assertEqual(lines[-1], "OK")
		self.assertIn("chain OK", lines[0])
		self.assertIn("Seal: intact and valid, trusted", lines)

	def test_tampered_event_is_reported(self):
		name = self.completed()
		event = frappe.get_all("Sign Event", filters={"envelope": name, "seq": 4}, pluck="name")[0]
		frappe.db.set_value("Sign Event", event, "ip", "10.6.6.6", update_modified=False)
		code, lines = commands.run_verify(name)
		self.assertEqual(code, 1)
		self.assertIn("First bad event: #4 (hash does not match the event's contents)", lines)
		self.assertEqual(lines[-1], "FAILED")

	def test_tampered_signed_pdf_is_reported(self):
		name = self.completed()
		path = frappe.get_doc(
			"File", frappe.db.get_value("Sign Envelope", name, "signed_file")
		).get_full_path()
		with open(path, "ab") as handle:
			handle.write(b"\n%tampered\n")
		code, lines = commands.run_verify(name)
		self.assertEqual(code, 1)
		self.assertIn("Problem: The signed PDF does not match its recorded SHA-256", lines)

	def test_missing_intermediate_is_reported(self):
		name = self.completed()
		row = frappe.get_doc("Sign Envelope", name).recipients[0]
		os.remove(frappe.get_doc("File", row.intermediate_file).get_full_path())
		code, lines = commands.run_verify(name)
		self.assertEqual(code, 1)
		self.assertTrue(any("missing" in line for line in lines), lines)

	def test_unknown_envelope(self):
		self.assertEqual(commands.run_verify("SIGN-2026-99999"), (2, ["SIGN-2026-99999: not found"]))

	def test_command_is_registered(self):
		self.assertIn("verify", commands.frappe_sign.commands)
		result = CliRunner().invoke(commands.frappe_sign, ["verify", "--help"])
		self.assertEqual(result.exit_code, 0)
		self.assertIn("audit chain", result.output)
