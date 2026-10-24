# CLAUDE.md: Frappe Sign

Instructions for Claude Code working in this repository. Read this file fully at the start of every session.

## What this is

`frappe_sign` is an e-signature app for Frappe and ERPNext v16. Users send any document (usually from its Print Format) for signature; external signers sign via link with optional OTP; the final PDF is sealed with PAdES and written back to the source document.

Source of truth, in this order:

1. `docs/DECISIONS.md`: why things are the way they are. Do not contradict an Accepted decision. If you believe one is wrong, stop and propose a change instead of diverging.
2. `docs/DESIGN.md`: data model, flows, security, APIs.
3. `docs/ARCHITECTURE.md`: layers, layout, import rules.
4. `docs/PLAN.md`: phases, task IDs, gates. Work only on the current phase.

## Golden rules

1. **Clean room.** Never copy code from nesscale_sign or any AGPL project. Never add PyMuPDF (`fitz`), iText or any AGPL or GPL dependency to Python or JS. LGPL is allowed only for the libraries listed in D2.
2. **v16.0.0 floor.** Only use Frappe and ERPNext APIs that exist in v16.0.0. For anything newer, add a feature-detected shim in `frappe_sign/compat.py` (`hasattr` or guarded import). Never compare version strings. When unsure whether an API exists in v16.0.0, check the `v16.0.0` tag source before using it.
3. **ERPNext is optional.** Core code never imports `erpnext`. ERPNext-specific code lives in `frappe_sign/erpnext/`, activated through hooks only when `"erpnext" in frappe.get_installed_apps()`. Read ERPNext document fields with `doc.get()`.
4. **Layers.** Controllers validate and guard state only. They may import `utils/`, `exceptions`, `compat` and `crypto/pkcs12.py`. Business logic lives in `services/`. `api/` functions are thin. `pdf/` is pure (only `source.py` and `certificate.py` import `frappe`) and raises `PdfError` from `pdf/types.py`. `jobs/` are transaction boundaries only, and every enqueued function is a `jobs/` entry point.
5. **No commits in services.** Never call `frappe.db.commit()` outside `jobs/` entry points and scheduler functions.
6. **Permissions.** `ignore_permissions=True` is allowed only in `services/signing.py` after a guest token or session check, each time with a comment naming that check. Semgrep enforces this.
7. **Secrets.** Store tokens, session secrets and OTPs as SHA-256 hashes only. Certificate passwords use Password fields and `get_password`. Never log secrets, tokens, OTPs or PDF bytes.
8. **Private files.** Every File the app creates has `is_private=1`.
9. **Immutability.** Sign Event, Sign Capture and Sign Template Version are insert-only. An envelope past Draft only changes through service functions using `db_set`.
10. **Heavy work in jobs.** Rendering, sealing, post-sign actions, bulk sends and trigger work are enqueued (`enqueue_after_commit=True`). Sealing uses `job_id=f"frappe_sign::seal::{envelope}"` and `deduplicate=True`. Domain event handlers run in jobs (D17). The one exception: `signing.finish` renders the intermediate PDF in the request, under the envelope row lock (D3).
11. **Never swallow errors.** Catch only to record (Sign Trigger Log, Sign Event payload, Error Log with title `Frappe Sign: <area>`) and notify. No bare `except: pass`.
12. **Writing style.** No em dashes in code comments, docs, UI copy or commit messages. Use colons, commas or parentheses.

## Stack and versions

- Python `>=3.14,<3.15`, Frappe and ERPNext `>=16.0.0,<17.0.0`, MariaDB, Redis.
- Python deps: pypdf, reportlab, pyhanko, arabic-reshaper, python-bidi, qrcode. Test-only: pypdfium2.
- Frontend: Node `>=24`, Vue 3 `<script setup>` + TypeScript strict, frappe-ui (pinned), Tailwind, vue-router, Pinia (designer only), pdfjs-dist, signature_pad. Vitest, Playwright.

## Naming

- App `frappe_sign`, module "Frappe Sign", DocTypes prefixed `Sign `.
- Hooks: `frappe_sign_resolvers`, `frappe_sign_events`, `frappe_sign_post_sign_actions`.
- Routes: `/sign/...` (staff), `/s/<token>` (guest), `/sign-verify` (public).
- Job ids and cache keys prefixed `frappe_sign::`.
- Error Log titles prefixed `Frappe Sign: `.

## Commands

The bench is at `~/Projects/frappe-bench`. Sites:

- `sign.localhost`: Frappe, ERPNext and frappe_sign. The default for all commands.
- `sign-core.localhost`: Frappe and frappe_sign only. Run the tests here too, to check the "without ERPNext" case.

Never install frappe_sign on, migrate or run tests against any other site on this bench.

```bash
# Backend
bench --site sign.localhost migrate
bench --site sign.localhost run-tests --app frappe_sign
bench --site sign.localhost run-tests --app frappe_sign --module frappe_sign.tests.unit.test_overlay
bench --site sign.localhost frappe-sign verify SIGN-2026-00001
bench build --app frappe_sign

# Frontend (from apps/frappe_sign/frontend)
yarn dev          # Vite dev server proxied to the bench
yarn build
yarn test         # Vitest
yarn typecheck    # vue-tsc --noEmit
yarn lint

# Quality
pre-commit run --all-files
mypy frappe_sign/services frappe_sign/pdf frappe_sign/crypto
```

## Testing rules

- Write tests before implementation for `pdf/`, `crypto/` and `services/`.
- Unit tests subclass `frappe.tests.UnitTestCase`; DB tests subclass `frappe.tests.IntegrationTestCase`.
- ERPNext tests live in `tests/erpnext/` and skip when ERPNext is not installed.
- Coordinates are tested against `tests/fixtures/coords.json` in both Python and Vitest. If you change coordinate math on one side, change and test the other side in the same PR.
- Sealed output must validate with pyHanko in tests.
- Coverage target: 85% on `services/`, `pdf/`, `crypto/`.

## Workflow

- Work task by task from `docs/PLAN.md`; reference the task ID in commit messages: `P1.4: seal PDFs with PAdES-B-LT`.
- Never add `Co-Authored-By: Claude` or any Claude attribution to commits or PR descriptions.
- Before writing code for a task, state a short plan (files, functions, tests). Use plan mode for anything touching more than three files.
- After each task: run the relevant tests, `pre-commit`, and typecheck; fix failures before moving on.
- Tick the task in `docs/PLAN.md` when done.
- At a phase gate, stop and summarize: what passed, what is open, anything that needs a human (Adobe check, pilot setup).
- If a decision in `docs/DECISIONS.md` needs changing, propose the edit and wait for approval.

## DocType conventions

- Create DocTypes as JSON under `frappe_sign/frappe_sign/doctype/` with controllers; keep `naming_rule`, permissions and indexes in JSON.
- Add DB indexes on `Sign Envelope Recipient.token_hash`, `Sign Session.session_hash`, `Sign Event.envelope`, `Sign Envelope.reference_doctype + reference_name`.
- `company` fields are Data in JSON; `erpnext/setup.py` converts them to Link Company with Property Setters when ERPNext is installed (rules in DESIGN.md 2.1).
- Schema changes that reshape data need a patch in `patches.txt` and a test.

## Frontend conventions

- Use frappe-ui components before writing custom ones.
- Server calls through `createResource` / `createListResource` / `createDocumentResource`, or `shared/api.ts` for guest calls (adds `X-Sign-Session`).
- Switch UI states on the backend error `code`, never on message text.
- All strings through `__()`; use Tailwind logical properties for RTL.
- Guest bundle must stay under 250 KB gzipped excluding the pdf.js worker; check after adding dependencies.