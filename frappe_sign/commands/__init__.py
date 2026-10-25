"""bench frappe-sign commands.

    bench --site sign.localhost frappe-sign verify SIGN-2026-00001

`verify` recomputes the audit hash chain and the PDF hashes, validates the seal, prints OK or the
first problem, and exits with status 1 when anything does not match (DESIGN 5.5).
"""

import click
import frappe
from frappe.commands import get_site, pass_context

from frappe_sign.services import verify as verify_service


def run_verify(envelope: str) -> tuple[int, list[str]]:
	"""Exit code and output lines for one envelope. The site must be connected."""
	if not frappe.db.exists("Sign Envelope", envelope):
		return 2, [f"{envelope}: not found"]
	check = verify_service.check_envelope(envelope)
	lines = [f"{envelope}: {check.events} events, chain {'OK' if check.chain_ok else 'BROKEN'}"]
	if check.first_bad_seq is not None:
		lines.append(f"First bad event: #{check.first_bad_seq} ({check.chain_reason})")
	lines.extend(f"Problem: {problem}" for problem in check.problems if not problem.startswith("Audit chain"))
	if check.seal_trusted is not None:
		lines.append(
			f"Seal: intact and valid, {'trusted' if check.seal_trusted else 'not chained to a trusted root'}"
		)
	lines.append("OK" if check.ok else "FAILED")
	return (0 if check.ok else 1), lines


@click.group("frappe-sign")
def frappe_sign() -> None:
	"""Frappe Sign tools."""


@frappe_sign.command("verify")
@click.argument("envelopes", nargs=-1, required=True)
@pass_context
def verify(context, envelopes) -> None:
	"""Verify the audit chain, PDF hashes and seal of one or more envelopes."""
	site = get_site(context)
	frappe.init(site=site)
	frappe.connect()
	worst = 0
	try:
		for envelope in envelopes:
			code, lines = run_verify(envelope)
			for line in lines:
				click.echo(line)
			worst = max(worst, code)
	finally:
		frappe.destroy()
	if worst:
		raise SystemExit(worst)


commands = [frappe_sign]
