"""Health panel (P3.7): what a Sign Manager should know before a customer finds out.

Five checks, each `ok`, `info`, `warn` or `fail`: seal certificates, timestamp servers, the oldest
queued seal, trigger failures in the last 24 hours, and the sender's SPF and DKIM records. The
report holds no secret. Timestamp servers are real network calls, so their result is cached for
ten minutes; "Check again" refreshes it. Reads use the database after a role check, because a Sign
Manager cannot open a Sign Certificate in Desk.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, now_datetime

from frappe_sign.crypto import tsa
from frappe_sign.services import certificates, settings, setup

VIEW_ROLES = ["Sign Manager", "System Manager"]
TSA_CACHE = "frappe_sign::health::tsa"
TSA_TTL_SECONDS = 600
SEAL_WARN_DAYS = 30
SEAL_QUEUE_WARN_MINUTES = 15
SEAL_QUEUE_FAIL_MINUTES = 60
# Selectors that mail providers commonly use; DKIM cannot be looked up without knowing one.
DKIM_SELECTORS = ("default", "google", "selector1", "selector2", "mail", "k1", "dkim", "s1", "mandrill")
ORDER = {"ok": 0, "info": 1, "warn": 2, "fail": 3}


def report(refresh: bool = False) -> dict[str, Any]:
	frappe.only_for(VIEW_ROLES)
	checks = [
		seal_check(),
		tsa_check(refresh),
		seals_check(),
		triggers_check(),
		email_check(),
	]
	return {
		"status": max((check["status"] for check in checks), key=ORDER.__getitem__),
		"checked_on": str(now_datetime()),
		"checks": checks,
	}


def check(key: str, title: str, status: str, detail: str, hint: str = "") -> dict[str, str]:
	return {"key": key, "title": title, "status": status, "detail": detail, "hint": hint}


# Seal certificates


def seal_check() -> dict[str, str]:
	title = _("Company seal")
	profiles = frappe.get_all("Sign Profile", fields=["name", "sealing_certificate"], order_by="creation asc")
	if not profiles:
		return check(
			"seal", title, "warn", _("No company profile yet."), _("Create a seal in Settings, Company.")
		)
	worst, lines = "ok", []
	for profile in profiles:
		status, line = profile_seal(profile)
		lines.append(line)
		worst = max(worst, status, key=ORDER.__getitem__)
	hint = (
		"" if worst == "ok" else _("Upload a new certificate in Settings, Company before the old one ends.")
	)
	return check("seal", title, worst, "; ".join(lines), hint)


def profile_seal(profile: Any) -> tuple[str, str]:
	if not profile.sealing_certificate:
		return "fail", _("{0}: no seal certificate").format(profile.name)
	details = certificates.seal_details(profile.sealing_certificate)
	valid_to = details["valid_to"]
	if details["expired"]:
		return "fail", _("{0}: the seal has ended").format(profile.name)
	if not valid_to:
		return "warn", _("{0}: the end date is not known yet").format(profile.name)
	days = (getdate(str(valid_to)) - getdate()).days
	if days <= SEAL_WARN_DAYS:
		return "warn", _("{0}: the seal ends in {1} days").format(profile.name, days)
	return "ok", _("{0}: valid until {1}").format(profile.name, valid_to)


# Timestamp servers


def probe_tsa(url: str) -> str | None:
	return tsa.probe(url)


def tsa_check(refresh: bool) -> dict[str, str]:
	title = _("Timestamp servers")
	urls = settings.tsa_urls()
	results = cached_tsa(urls) if not refresh else None
	if results is None:
		results = {url: probe_tsa(url) for url in urls}
		frappe.cache.set_value(TSA_CACHE, {"urls": urls, "results": results}, expires_in_sec=TSA_TTL_SECONDS)
	failed = {url: error for url, error in results.items() if error}
	if not failed:
		return check("tsa", title, "ok", _("All {0} servers answer.").format(len(results)))
	detail = "; ".join(f"{url}: {error}" for url, error in failed.items())
	hint = _("Sealing tries the servers in order. Add another server in Settings, Advanced.")
	status = "warn" if len(failed) < len(results) else "fail"
	return check("tsa", title, status, detail, hint)


def cached_tsa(urls: list[str]) -> dict[str, str | None] | None:
	value = frappe.cache.get_value(TSA_CACHE)
	return value["results"] if value and value.get("urls") == urls else None


# Seals in the queue


def seals_check() -> dict[str, str]:
	title = _("Sealing queue")
	rows = frappe.get_all(
		"Sign Envelope",
		filters={"sealing_state": ["in", ["Queued", "Sealing", "Failed"]]},
		fields=["name", "sealing_state", "modified"],
		order_by="modified asc",
	)
	if not rows:
		return check("seals", title, "ok", _("Nothing is waiting to be sealed."))
	failed = [row for row in rows if row.sealing_state == "Failed"]
	oldest = rows[0]
	minutes = int((now_datetime() - oldest.modified) / timedelta(minutes=1))
	detail = _("The oldest, {0}, has waited {1} minutes.").format(oldest.name, minutes)
	if failed:
		detail = _("{0} seals failed ({1}).").format(len(failed), failed[0].name) + " " + detail
		return check("seals", title, "fail", detail, _("Open the request and use Retry seal."))
	if minutes >= SEAL_QUEUE_FAIL_MINUTES:
		return check("seals", title, "fail", detail, _("Check that a long-queue worker is running."))
	status = "warn" if minutes >= SEAL_QUEUE_WARN_MINUTES else "ok"
	return check("seals", title, status, detail)


# Trigger failures


def triggers_check() -> dict[str, str]:
	title = _("Automatic sending")
	count = frappe.db.count(
		"Sign Trigger Log", {"status": "Failed", "creation": [">", now_datetime() - timedelta(hours=24)]}
	)
	if not count:
		return check("triggers", title, "ok", _("No failed runs in the last 24 hours."))
	return check(
		"triggers",
		title,
		"warn",
		_("{0} failed runs in the last 24 hours.").format(count),
		_("Open Sign Trigger Log in Desk and filter by Failed to see why."),
	)


# Sender email: SPF and DKIM


def sender_addresses() -> dict[str, str]:
	"""Sender address by company; "" is the site's default account when no profile has its own."""
	found = {}
	for name in frappe.get_all("Sign Profile", pluck="name"):
		address = setup.outgoing_email(name)
		if address:
			found[name] = address
	if not found and (address := setup.outgoing_email(None)):
		found[""] = address
	return found


def lookup_txt(name: str) -> list[str] | None:
	"""TXT records of `name`; [] when there are none, None when DNS cannot be asked (no resolver)."""
	try:
		import dns.exception
		import dns.resolver
	except ImportError:
		return None
	try:
		answers = dns.resolver.resolve(name, "TXT", lifetime=3)
	except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
		return []
	except dns.exception.DNSException:
		return None
	return ["".join(part.decode(errors="replace") for part in rdata.strings) for rdata in answers]


def email_check() -> dict[str, str]:
	title = _("Email delivery")
	senders = sender_addresses()
	hint = _(
		"Invitations land in spam unless the sending domain publishes an SPF record that lists your mail "
		"server and a DKIM key. Ask your mail provider for both."
	)
	if not senders:
		return check("email", title, "warn", _("No sender email account is set up."), hint)
	domains = sorted({address.rsplit("@", 1)[-1].lower() for address in senders.values() if "@" in address})
	problems, unknown = [], False
	for domain in domains:
		spf = lookup_txt(domain)
		if spf is None:
			unknown = True
			continue
		if not any(record.lower().startswith("v=spf1") for record in spf):
			problems.append(_("{0} has no SPF record").format(domain))
		elif not has_dkim(domain):
			problems.append(_("no DKIM key found for {0} (only common selectors are tried)").format(domain))
	if unknown:
		return check(
			"email", title, "info", _("The DNS records could not be checked from this server."), hint
		)
	if problems:
		status = "warn" if any("SPF" in problem for problem in problems) else "info"
		return check("email", title, status, "; ".join(problems), hint)
	return check("email", title, "ok", _("SPF and DKIM found for {0}.").format(", ".join(domains)))


def has_dkim(domain: str) -> bool:
	for selector in DKIM_SELECTORS:
		records = lookup_txt(f"{selector}._domainkey.{domain}") or []
		if any("v=dkim1" in record.lower() for record in records):
			return True
	return False
