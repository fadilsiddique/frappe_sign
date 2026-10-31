"""Load test (P3.8): a 150-page PDF and 50 concurrent signers. Run on a site with allow_tests:

    bench --site sign.localhost execute frappe_sign.tests.loadtest.run --kwargs '{"workers": 4}'

Three phases, each in fresh worker processes so peak memory belongs to one operation:

1. One envelope on the 150-page PDF, signed by two people and sealed (offline TSA, so the number is
   CPU and not network). Gives the cost of `finish` (the intermediate render, D3) and of sealing.
2. 50 envelopes, one signer each, all started at once on `workers` processes (a gunicorn pool).
3. One envelope with 50 parallel signers finishing at once: the row lock puts the 50 renders in line,
   which is the worst case for D3.

Everything it creates is deleted at the end. It commits, so run it only on a test site.
"""

from __future__ import annotations

import multiprocessing
import os
import platform
import resource
import time
from typing import Any
from unittest.mock import patch

import frappe
from frappe.utils import now_datetime

from frappe_sign.services import envelope as envelope_service
from frappe_sign.tests.cleanup import purge_envelope, purge_profile, purge_since, purge_template
from frappe_sign.tests.e2e import require_test_site
from frappe_sign.tests.factories import make_email_account, make_profile, signature_field, test_company
from frappe_sign.tests.signing_helpers import capture_tokens, make_draft, publish_template, send_now
from frappe_sign.tests.unit.test_overlay import signature_png
from frappe_sign.utils.request import Client
from frappe_sign.utils.users import run_as

PDF = "many_pages_150.pdf"
HEAVY_PDF = "loadtest_heavy_150.pdf"  # generated: 150 pages with a photo each, about 15 MB
CLIENT = Client(ip="203.0.113.50", user_agent="loadtest")


def build_heavy_pdf() -> bytes:
	"""150 A4 pages, each with a noisy JPEG and some text: the largest a 20 MB upload limit allows,
	and much heavier to copy and render than the text-only fixture."""
	import io
	import random

	from PIL import Image
	from reportlab.lib.pagesizes import A4
	from reportlab.lib.utils import ImageReader
	from reportlab.pdfgen import canvas

	rng = random.Random(7)
	out = io.BytesIO()
	pdf = canvas.Canvas(out, pagesize=A4, pageCompression=1)
	for page in range(150):
		noise = Image.frombytes("RGB", (360, 500), bytes(rng.randrange(256) for _ in range(360 * 500 * 3)))
		jpeg = io.BytesIO()
		noise.save(jpeg, "JPEG", quality=60)
		jpeg.seek(0)
		pdf.drawImage(ImageReader(jpeg), 40, 200, width=515, height=620)
		for line in range(12):
			pdf.drawString(
				40, 180 - line * 12, f"Page {page + 1}, clause {line + 1}: the parties agree to the terms."
			)
		pdf.showPage()
	pdf.save()
	return out.getvalue()


def rss_mb() -> float:
	"""Peak resident memory of this process in MB (macOS reports bytes, Linux kilobytes)."""
	peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
	return round(peak / (1024 * 1024 if platform.system() == "Darwin" else 1024), 1)


def current_mb() -> float:
	import psutil

	return round(psutil.Process().memory_info().rss / (1024 * 1024), 1)


# Worker processes


def init_worker(site: str, sites_path: str) -> None:
	frappe.init(site=site, sites_path=sites_path)
	frappe.connect()


def timed(steps: dict[str, float], name: str, work):
	start = time.perf_counter()
	result = work()
	steps[name] = round(time.perf_counter() - start, 3)
	return result


def sign_task(job: dict[str, Any]) -> dict[str, Any]:
	"""open, consent, one signature, finish: what a signer's browser does."""
	from frappe_sign.services import signing

	steps: dict[str, float] = {}
	began = time.perf_counter()
	with patch("frappe.enqueue"):
		opened = timed(steps, "open", lambda: signing.open(job["token"], CLIENT))
		session = opened["session"]
		timed(steps, "consent", lambda: signing.consent(session, opened["consent"]["version"], CLIENT))
		timed(
			steps,
			"capture",
			lambda: signing.save_capture(session, job["field"], "Draw", signature_png(), client=CLIENT),
		)
		result = timed(steps, "finish", lambda: signing.finish(session, CLIENT))
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (a web request commits at its end)
	return {
		"steps": steps,
		"seconds": round(time.perf_counter() - began, 3),
		"done": time.perf_counter(),
		"completed": result["completed"],
		"peak_mb": rss_mb(),
		"pid": os.getpid(),
	}


def seal_task(job: dict[str, Any]) -> dict[str, Any]:
	"""The seal job on a completed envelope, with the offline test PKI."""
	from frappe_sign.jobs import seal as seal_job
	from frappe_sign.tests.integration.test_sealing import offline_seal

	before = current_mb()
	start = time.perf_counter()
	with offline_seal(), patch("frappe.enqueue"), run_as("Administrator"):
		seal_job.run(job["envelope"])
	return {
		"seconds": round(time.perf_counter() - start, 3),
		"peak_mb": rss_mb(),
		"before_mb": before,
		"state": frappe.db.get_value("Sign Envelope", job["envelope"], "sealing_state"),
	}


def pool(workers: int, site: str, sites_path: str):
	return multiprocessing.get_context("spawn").Pool(workers, init_worker, (site, sites_path))


# Phases


def send_envelope(version: str, recipients: list[dict], **payload) -> tuple[str, dict[str, str]]:
	with run_as("Administrator"):
		draft = make_draft(version, recipients=recipients, company=test_company(), **payload)
		# Creating and sending are two requests in the app: commit between them, so a retry after a
		# snapshot conflict (which rolls back) cannot take the new draft with it.
		frappe.db.commit()  # nosemgrep: frappe-manual-commit
		with capture_tokens() as box:
			send_now(draft.name)
	frappe.db.commit()  # nosemgrep: frappe-manual-commit (worker processes need committed rows)
	doc = frappe.get_doc("Sign Envelope", draft.name)
	# Only the signers whose turn it is were invited; the others get the same derived link later (D10).
	return draft.name, {
		row.role_label: box.tokens.get(row.name) or envelope_service.link_token(row.name, 1)
		for row in doc.recipients
	}


def phase_single(site: str, sites_path: str, version: str) -> dict[str, Any]:
	people = [
		{"role_label": "Customer", "full_name": "Ahmed Khan", "email": "ahmed@example.com"},
		{"role_label": "Company", "full_name": "Fatima Ali", "email": "fatima@example.com"},
	]
	start = time.perf_counter()
	name, tokens = send_envelope(version, people)
	sent = round(time.perf_counter() - start, 3)
	with pool(1, site, sites_path) as workers:
		customer = workers.apply(sign_task, ({"token": tokens["Customer"], "field": "customer_signature"},))
		company = workers.apply(sign_task, ({"token": tokens["Company"], "field": "company_signature"},))
		seal = workers.apply(seal_task, ({"envelope": name},))
	return {"create_and_send_seconds": sent, "customer": customer, "company": company, "seal": seal}


def phase_envelopes(site: str, sites_path: str, version: str, workers: int, signers: int) -> dict[str, Any]:
	jobs = []
	for index in range(signers):
		people = [
			{"role_label": "Customer", "full_name": f"Signer {index}", "email": f"s{index}@example.com"},
			{"role_label": "Company", "full_name": "Fatima Ali", "email": "fatima@example.com"},
		]
		_name, tokens = send_envelope(version, people)
		jobs.append({"token": tokens["Customer"], "field": "customer_signature"})
	return burst(site, sites_path, workers, jobs)


def pdf_name() -> str:
	return HEAVY_PDF if os.path.exists(heavy_path()) else PDF


def heavy_path() -> str:
	return os.path.join(os.path.dirname(__file__), "fixtures", "pdfs", HEAVY_PDF)


def install_heavy_fixture() -> None:
	"""Write the generated PDF next to the other fixtures; run() removes it again."""
	# A fixed path inside the test fixtures folder, never user input.
	with open(heavy_path(), "wb") as handle:  # nosemgrep: frappe-security-file-traversal
		handle.write(build_heavy_pdf())


def phase_one_envelope(site: str, sites_path: str, workers: int, signers: int) -> dict[str, Any]:
	roles = [
		{"role_label": f"Signer {n}", "kind": "Signer", "signer_source": "Ask at Send", "routing_order": 1}
		for n in range(signers)
	]
	fields = [
		signature_field(
			field_key=f"sig_{n}",
			role_label=f"Signer {n}",
			page=1 + n % 3,
			x=0.05 + 0.3 * (n % 3),
			y=0.05 + 0.15 * (n // 3 % 6),
			w=0.25,
			h=0.06,
		)
		for n in range(signers)
	]
	with run_as("Administrator"):
		version = publish_template(signing_order="Parallel", roles=roles, fields=fields, pdf=pdf_name())
	people = [
		{"role_label": f"Signer {n}", "full_name": f"Signer {n}", "email": f"p{n}@example.com"}
		for n in range(signers)
	]
	name, tokens = send_envelope(version, people)
	jobs = [{"token": tokens[f"Signer {n}"], "field": f"sig_{n}"} for n in range(signers)]
	result = burst(site, sites_path, workers, jobs)
	frappe.db.rollback()
	doc = frappe.get_doc("Sign Envelope", name)
	result["sealing_state"] = doc.sealing_state
	result["signed"] = sum(1 for row in doc.recipients if row.status == "Signed")
	return result


def burst(site: str, sites_path: str, workers: int, jobs: list[dict]) -> dict[str, Any]:
	"""All jobs at once on `workers` processes; latency is measured from the shared start."""
	with pool(workers, site, sites_path) as processes:
		processes.map(init_noop, range(workers))  # every worker is up before the clock starts
		start = time.perf_counter()
		pending = [processes.apply_async(sign_task, (job,)) for job in jobs]
		results, errors = [], []
		for item in pending:
			try:
				results.append(item.get(timeout=900))
			except Exception as error:
				errors.append(f"{type(error).__name__}: {error}"[:200])
		wall = time.perf_counter() - start
	latencies = sorted(round(r["done"] - start, 2) for r in results)
	finish = sorted(r["steps"]["finish"] for r in results)
	return {
		"requests": len(jobs),
		"workers": workers,
		"errors": errors,
		"wall_seconds": round(wall, 1),
		"latency_p50": percentile(latencies, 50),
		"latency_p95": percentile(latencies, 95),
		"latency_max": latencies[-1] if latencies else None,
		"finish_p50": percentile(finish, 50),
		"finish_p95": percentile(finish, 95),
		"finish_max": finish[-1] if finish else None,
		"worker_peak_mb": max((r["peak_mb"] for r in results), default=None),
	}


def init_noop(_: int) -> int:
	return os.getpid()


def percentile(values: list[float], pct: int) -> float | None:
	if not values:
		return None
	index = min(len(values) - 1, round(pct / 100 * (len(values) - 1)))
	return round(values[index], 2)


# Entry point


def run(workers: int = 4, signers: int = 50, phases: str = "123", heavy: int = 0) -> dict[str, Any]:
	require_test_site()
	started = now_datetime()
	site, sites_path = frappe.local.site, frappe.local.sites_path
	envelopes: list[str] = []
	report: dict[str, Any] = {
		"machine": f"{platform.machine()}, {os.cpu_count()} cores",
		"python": platform.python_version(),
		"pdf": HEAVY_PDF if heavy else PDF,
		"workers": workers,
		"signers": signers,
	}
	try:
		with run_as("Administrator"):
			make_email_account(skip_smtp_check=True)
			make_profile(test_company())
			frappe.db.commit()  # nosemgrep: frappe-manual-commit (worker processes need committed rows)
			if heavy:
				install_heavy_fixture()
			version = publish_template(pdf=HEAVY_PDF if heavy else PDF)
			frappe.db.commit()  # nosemgrep: frappe-manual-commit
		report["parent_mb_before"] = current_mb()
		if "1" in phases:
			report["single_envelope"] = phase_single(site, sites_path, version)
		if "2" in phases:
			report["envelopes_in_parallel"] = phase_envelopes(site, sites_path, version, workers, signers)
		if "3" in phases:
			report["one_envelope_parallel_signers"] = phase_one_envelope(site, sites_path, workers, signers)
	finally:
		envelopes = frappe.get_all("Sign Envelope", filters={"creation": [">=", started]}, pluck="name")
		frappe.db.rollback()
		templates = set()
		for name in envelopes:
			templates.update(purge_envelope(name))
		templates.update(frappe.get_all("Sign Template", filters={"creation": [">=", started]}, pluck="name"))
		for template in templates:
			purge_template(template)
		purge_profile(test_company())
		purge_since(started)
		frappe.db.commit()  # nosemgrep: frappe-manual-commit (the purge must persist)
		report["cleaned_envelopes"] = len(envelopes)
		if os.path.exists(heavy_path()):
			os.remove(heavy_path())
	return report
