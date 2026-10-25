# Claude Code prompts for Frappe Sign

How to use:

1. Create the app with `bench new-app frappe_sign` (or let the Phase 0 prompt do it), then copy `CLAUDE.md` to the app root and the four files into `docs/`.
2. Open Claude Code in `apps/frappe_sign`.
3. Paste the **Kickoff prompt** once, then the prompt for the current phase.
4. Start a fresh session for each phase. `CLAUDE.md` and `docs/` carry the context between sessions.

---

## Kickoff prompt (paste once, first session)

```text
You are the lead engineer building frappe_sign, an e-signature app for Frappe and ERPNext v16.

Before doing anything:
1. Read CLAUDE.md fully.
2. Read docs/DECISIONS.md, docs/ARCHITECTURE.md, docs/DESIGN.md and docs/PLAN.md fully.
3. Summarize back to me in under 15 bullets: the layers and their import rules, the 16 DocTypes, the signing and sealing flow, the v16.0.0 compatibility rule, and the golden rules you must never break.
4. List anything in the docs that is ambiguous or contradictory, with your proposed resolution. Do not write code yet.

Environment:
- Bench path: ~/frappe-bench (tell me if you find otherwise)
- Site: sign.localhost
- Frappe and ERPNext are on version-16; a second bench pinned to v16.0.0 is used by CI for the floor check.

Wait for my confirmation after the summary.
```

---

## Phase 0 prompt

```text
Execute Phase 0 of docs/PLAN.md (tasks P0.1 to P0.8).

Rules:
- Follow CLAUDE.md strictly. Work task by task in ID order.
- For each task: state a short plan (files, functions, tests), implement, run tests and pre-commit, fix failures, tick the task in docs/PLAN.md, commit as "P0.x: <summary>".
- P0.4: create all 16 DocTypes from docs/DESIGN.md section 2 as JSON with controllers. Implement the integrity rules from section 2.6 now, with tests. Keep business logic out of controllers.
- P0.5: scaffold the Vite project in frontend/ with two entries (src/staff, src/guest), vue-router bases /sign and /s, frappe-ui pinned, Tailwind preset, post-build copy of HTML shells into frappe_sign/www/, and www/sign.py + www/s.py boot context. Add website_route_rules.
- P0.6: GitHub Actions matrix {frappe+erpnext v16.0.0 tags, version-16 branch heads} x {with ERPNext, without ERPNext}. Use MariaDB and Redis service containers.
- P0.7 / P0.8: generate fixtures with scripts committed under tests/fixtures/scripts/ so they are reproducible.
- Verify every Frappe API you use exists in the v16.0.0 tag.

At the end, check Gate 0 and report: what passed, what failed, what needs me.
```

---

## Phase 1 prompt

```text
Execute Phase 1 of docs/PLAN.md (tasks P1.1 to P1.18), in the weekly order given.

Rules:
- Follow CLAUDE.md strictly. Tests first for pdf/, crypto/ and services/.
- pdf/ modules are pure: bytes in, bytes out, dataclasses from pdf/types.py. Only source.py and certificate.py may import frappe.
- Coordinates: implement pdf/types.py conversion and frontend shared/coords.ts against the same tests/fixtures/coords.json. Rotation and CropBox offsets must be handled.
- Arabic: shape with arabic-reshaper + python-bidi, draw with bundled Noto Naskh Arabic. Add a fixture test with an Arabic name.
- Sealing: PAdES-B-LT via pyHanko with Pkcs12Signer behind the Signer protocol (DESIGN 5.3), TSA URLs from Sign Settings with fallback. Implement the row lock, sealing_state and deduplicated job exactly as DESIGN 5.4, with a two-thread concurrency test.
- Audit chain exactly as DESIGN 5.5, including seq assignment under the row lock.
- Guest API: hashed tokens, X-Sign-Session header (no cookies), @rate_limit on every endpoint, recipient-scoped responses (DESIGN 5.2). Write the security tests listed in DESIGN 9.
- Guest SPA must work at 390 px width; add the Playwright test.
- Designer must round-trip: fields placed in the browser land at identical positions in the server overlay (fixture test).
- Commit per task as "P1.x: <summary>" and tick tasks in docs/PLAN.md.

Stop at Gate 1. Produce a signed sample PDF at tests/output/sample_signed.pdf for my manual Adobe Reader check, report coverage for pdf/, crypto/ and services/, and list anything open.
```

---

## Phase 2 prompt

```text
Execute Phase 2 of docs/PLAN.md (tasks P2.1 to P2.11).

Rules:
- Follow CLAUDE.md strictly. ERPNext code only under frappe_sign/erpnext/, loaded via hooks when ERPNext is installed. Core keeps working without ERPNext (CI matrix proves it).
- Print Format rendering via frappe.get_print(doctype, name, print_format, letterhead=..., as_pdf=True); respect the Print Format's pdf_generator. Test anchors with both wkhtmltopdf and chrome.
- sign_field() Jinja helper and anchors exactly as DESIGN 4.2. Test a Quotation Print Format with 3 items and 40 items.
- Resolvers per DESIGN 4.3 via the frappe_sign_resolvers hook. Before using any ERPNext field name, confirm it exists in the ERPNext v16.0.0 DocType JSON. Use doc.get(); missing data means "unresolved", never an exception.
- desk.js: form button and indicator on form-refresh, print view button, list bulk action, send dialog with frappe.ui.Dialog. No Vue in Desk.
- Write-back and post-sign actions per DESIGN 4.5 and 4.6. Post-sign actions run in a job as the sender; failures are logged and notified, never rolled into the signature.
- Sign Trigger dispatcher per D8: one doc_events["*"] handler, cached DocType gate, enqueue_after_commit, Sign Trigger Log for every run. Add a test asserting non-matching DocTypes cost one cache lookup and no DB query.
- Commit per task as "P2.x: <summary>" and tick tasks in docs/PLAN.md.

Stop at Gate 2 and give me a pilot setup checklist (Print Format edits, templates, Sign Profile, certificate, Email Account, roles).
```

---

## Phase 3 prompt

```text
Execute Phase 3 of docs/PLAN.md (tasks P3.1 to P3.9).

Rules:
- Follow CLAUDE.md strictly.
- WhatsApp is a soft dependency on frappe_whatsapp: feature hidden when not installed.
- Scheduler jobs tested with frozen time.
- RemoteSigner (PKCS#11 and CSC) behind the Signer protocol; test PKCS#11 with SoftHSM in CI.
- Full Arabic UI with RTL using Tailwind logical properties; screenshot each screen in Arabic for my review.
- Security review: walk DESIGN section 5 point by point and report each control as implemented and tested, or a gap.
- Load test: 150-page PDF and 50 concurrent signers; report timings and memory.
- Commit per task as "P3.x: <summary>" and tick tasks in docs/PLAN.md.

Stop at Gate 3 with release notes for v1.0.0.
```

---

## Useful one-off prompts

**Resume after a break**

```text
Read CLAUDE.md and docs/PLAN.md. Tell me which tasks are ticked, which task is next, and any failing tests (run them). Then continue with the next task.
```

**Review before merging a phase**

```text
Review the diff since the last gate against CLAUDE.md golden rules and docs/DECISIONS.md. List every violation with file and line, then fix them. Pay special attention to: ignore_permissions, frappe.db.commit, imports from erpnext in core, any API not present in Frappe v16.0.0, secrets in logs, public files, swallowed exceptions, em dashes.
```

**Compatibility check**

```text
For every frappe.* and erpnext.* symbol imported or called in frappe_sign/, confirm it exists in the v16.0.0 tags of frappe and erpnext. Output a table: symbol, file, exists in v16.0.0 (yes/no), fix if no.
```