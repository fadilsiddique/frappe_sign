# Frappe Sign: Decisions

Architecture Decision Records for `frappe_sign`. Each entry states the decision, why, and what was rejected. Change a decision by editing its entry in a PR and adding a dated note under "History", never by silently diverging in code.

Status values: **Accepted**, **Proposed**, **Superseded**.

---

## D1. Clean-room build, no code from nesscale_sign

- **Status:** Accepted
- **Decision:** `frappe_sign` is written from scratch. nesscale_sign is a feature reference only. No code, templates, CSS or JSON are copied.
- **Why:** nesscale_sign is AGPL-3.0. Copying any of it makes `frappe_sign` AGPL. Its frontend source is also not in the repo (compiled bundle only), so there is nothing maintainable to fork.
- **Rejected:** Forking and refactoring.

## D2. PDF stack: pypdf, reportlab, pyHanko, pdf.js

- **Status:** Accepted
- **Decision:**
  - `pypdf` (BSD) for reading, sanitizing, merging pages, positioned text extraction.
  - `reportlab` (BSD) for drawing field overlays.
  - `pyHanko` (MIT) for PAdES signing, timestamps and validation.
  - `pdfjs-dist` (Apache-2.0) in the browser.
  - `arabic-reshaper` (MIT) + `python-bidi` (LGPL, used unmodified as a library) for Arabic shaping.
  - LGPL is allowed only for the libraries listed here, used unmodified. GPL and AGPL are never allowed.
- **Why:** All permissive, maintained, and pyHanko is the reference PAdES implementation in Python.
- **Rejected:** PyMuPDF (AGPL or paid commercial license), iText (AGPL), pdf-lib in browser for final output (server must be the source of truth).

## D3. One platform seal at completion (PAdES-B-LT)

- **Status:** Accepted
- **Decision:** When the last signer finishes, the final PDF (values flattened + certificate of completion pages) is sealed once with the Company's sealing certificate, an RFC 3161 timestamp and embedded revocation info (PAdES-B-LT). Per-signer integrity comes from SHA-256 hashes of the intermediate PDF each signer completed, recorded in the hash-chained audit log.
- **Intermediate PDF:** `services/signing.finish` renders the intermediate PDF inside the request, under the envelope row lock. This is the only PDF rendering outside a job. The lock puts parallel finishes in order, so each hash matches what that signer saw. The PDF is stored as a private File and is the PDF that the next signer sees. The P3.8 load test measures the cost. If it is too slow, propose a change that moves the render to a job.
- **Why:** Signers need no certificates. Adobe reports the seal as valid. Appending the certificate page after per-signer signatures would be reported by Adobe as a modification.
- **Rejected:**
  - Image-only stamping (not tamper-evident in PDF readers).
  - Incremental seal per signer (breaks with the certificate page).
  - Personal signer certificates (Phase 4, via UAE PASS).

## D4. ERPNext is a soft dependency

- **Status:** Accepted
- **Decision:** `required_apps = ["frappe"]` only. Everything ERPNext-specific lives in `frappe_sign/erpnext/` and is activated only when `"erpnext" in frappe.get_installed_apps()`. Core code never imports from `erpnext`.
- **Why:** Smaller blast radius, core testable on plain Frappe, usable by non-ERPNext Frappe apps (HRMS-only, custom apps), and keeps the GPL surface of ERPNext thin.
- **Rejected:** `required_apps = ["erpnext"]`.

## D5. Print Format is a first-class document source

- **Status:** Accepted
- **Decision:** Envelopes can be created from any Print Format using `frappe.get_print(doctype, name, print_format, letterhead=..., as_pdf=True)`. The Print Format's own `pdf_generator` setting (wkhtmltopdf or chrome) is respected. Uploaded PDFs remain supported.
- **Why:** This is the core ERPNext advantage over generic e-signature tools.
- **Rejected:** Upload-only.

## D6. PDF frozen at send

- **Status:** Accepted
- **Decision:** At send, the rendered PDF bytes are stored as a private File and their SHA-256 recorded. If the source document changes later, the envelope gets `source_changed = 1` and the sender is notified. The envelope content never changes.
- **Why:** A signed document must be exactly what was sent.
- **Rejected:** Re-rendering on open.

## D7. Field coordinates: normalized, plus anchors

- **Status:** Accepted
- **Decision:** Field rectangles are stored as `x, y, w, h` in the range 0..1, top-left origin, relative to the page's visible (CropBox, rotation-applied) area. Print Formats can also place fields with a `sign_field()` Jinja helper that emits invisible anchor markers, resolved to rectangles after rendering.
- **Why:** The same numbers drive pdf.js in the designer and the server overlay. Anchors survive layout changes (longer item tables).
- **Rejected:** Absolute pixel coordinates.

## D8. Auto-send triggers via one cached `*` dispatcher

- **Status:** Accepted
- **Decision:** `hooks.py` registers one `doc_events["*"]` dispatcher. It checks an O(1) cached set of DocTypes that have enabled Sign Triggers and returns immediately otherwise. Matching events enqueue work with `enqueue_after_commit=True`. Every run writes a Sign Trigger Log row, including failures, which are visible on the source document.
- **Why:** `hooks.py` is static and bench-wide, so per-site dynamic registration is impossible. The real problems in nesscale_sign were synchronous work inside the host transaction and silently swallowed errors, not the `*` hook itself.
- **Rejected:** Hard-coded per-DocType hooks (not configurable per site).

## D9. Frontend: Vue 3 + TypeScript + frappe-ui, two entry points

- **Status:** Accepted
- **Decision:** One Vite project in `frontend/` with two entries: staff app at `/sign`, guest signing app at `/s/<token>`. Source in the repo; build output gitignored.
- **Why:** Same stack as other Upscape products (Tailorly). Guest bundle stays small for phones.
- **Rejected:** jQuery Desk pages; one large bundle.

## D10. Guest access: hashed tokens, OTP, rate limits

- **Status:** Accepted
- **Decision:** Recipient token = HMAC-SHA256 of the recipient row and a token version under the site's `encryption_key` (base64url, 256 bits). Only its SHA-256 is stored. Reminders and the signer's own "Sign now" link re-derive the same token, so earlier emails keep working; resend raises the version, so the old link stops working. Optional OTP (email or WhatsApp) per template. Guest session secret sent in an `X-Sign-Session` header, kept in memory, never a cookie. Every guest endpoint uses `frappe.rate_limiter.rate_limit`.
- **Why:** A DB leak does not leak live links (the key is in `site_config.json`, not the database); brute force is capped; no CSRF surface for guests. Signers often open an older email after a reminder, so reminders must not break it.
- **Consequence:** Changing the site's `encryption_key` makes every open link invalid; senders then use resend.
- **Rejected:** Plain tokens in DB; link-only access; cookie sessions for guests; random tokens that every reminder replaces (the first Phase 1 build, which broke the links in earlier emails).

## D11. All PDFs private

- **Status:** Accepted
- **Decision:** Every File created by the app is `is_private = 1`. Guests download only through session-checked endpoints that stream with `Cache-Control: no-store`.
- **Rejected:** Public file URLs.

## D12. Multi-company

- **Status:** Accepted
- **Decision:** Sealing certificate, branding, sender Email Account and templates are scoped to a Company via Sign Profile.
- **Why:** UAE groups often run several Companies in one site.
- **Rejected:** Single global settings.

## D13. Naming

- **Status:** Accepted
- **Decision:** App `frappe_sign`, title "Frappe Sign", module "Frappe Sign". DocTypes prefixed `Sign ` (Sign Envelope, Sign Template, ...). Hooks prefixed `frappe_sign_`. Routes `/sign`, `/s/<token>`, `/sign-verify`.
- **Why:** Readable; avoids clashing with ERPNext's `Contract`.
- **Rejected:** Vendor prefixes like `NS`.

## D14. Services own business logic

- **Status:** Accepted
- **Decision:** DocType controllers only validate and guard state. All business rules live in `frappe_sign/services/`. Whitelisted API functions are thin adapters that parse input, call one service function, and shape output.
- **Why:** Testable without HTTP, one place per rule, reusable from Desk, SPA, triggers and other apps.
- **Rejected:** Logic in controllers or API files.

## D15. Compatible with every Frappe and ERPNext v16 release

- **Status:** Accepted
- **Decision:**
  - Supported range: Frappe `>=16.0.0,<17.0.0`; ERPNext (optional) `>=16.0.0,<17.0.0`.
  - Code may only use framework APIs that exist in **v16.0.0**. Verified present in v16.0.0: `frappe.get_print(..., as_pdf=True, letterhead=..., pdf_generator=...)`, `frappe.tests.UnitTestCase` and `IntegrationTestCase`, `frappe.enqueue(..., job_id=..., deduplicate=..., enqueue_after_commit=...)`, `frappe.db.after_commit`, `frappe.rate_limiter.rate_limit`, `frappe.qb`.
  - Anything newer goes through `frappe_sign/compat.py` with feature detection (`hasattr`, guarded import). Never compare version strings.
  - Python `>=3.14,<3.15` and Node `>=24`, matching Frappe v16.
  - CI runs a floor (`v16.0.0` tags) and a ceiling (`version-16` branch head), each with and without ERPNext.
- **Why:** Clients sit on different v16 minors; Frappe Cloud benches update at different times.
- **Rejected:** Targeting only recent minors (for example 16.50+).

## D16. Signer abstraction for certificates

- **Status:** Accepted
- **Decision:** `frappe_sign/crypto/signer.py` defines a `Signer` protocol. `Pkcs12Signer` (file-based) ships in Phase 1. `RemoteSigner` (PKCS#11 or Cloud Signature Consortium API, both supported by pyHanko) ships in Phase 3.
- **Why:** Adobe-trusted (AATL) document-signing certificates usually require hardware-held keys, so a `.p12` file alone will not give the green tick.
- **Rejected:** Hard-coding PKCS#12.

## D17. Domain event handlers run in jobs

- **Status:** Accepted
- **Decision:** `services/events.publish` enqueues each handler with `enqueue_after_commit=True` through `jobs/events.py`. The job entry point commits. Handlers never run in the publishing transaction or in a `frappe.db.after_commit` callback.
- **Why:** Handlers write data (write-back attaches files and calls `db_set`). Writes made in an after-commit callback are never committed, and services must not commit. A handler in its own job also cannot roll back a signature.
- **Rejected:** `frappe.db.after_commit` callbacks.

## D18. Plain-language staff app is the main surface

- **Status:** Accepted
- **Decision:** The UI calls an envelope a "Signature request" ("Request" for short); DocType names, fields and APIs keep the D13 names. Setup (company seal, profiles, enabled DocTypes, settings) and Print Format templates are done in the staff app at `/sign`, which uses a frappe-ui `Sidebar` shell. Desk keeps its forms for admins, plus the "Send for Signature" button on documents. The company brand color appears only on the guest signing page and in emails; the staff app stays neutral. `/sign/envelopes` becomes `/sign/requests`, with a redirect from the old path.
- **Why:** In the Phase 2 pilot setup the user could not find the order of setup steps across five Desk forms, could not make a Quotation template from `/sign/templates`, and did not know the words Envelope, CC, Party Contact or OTP mode.
- **Rejected:** Keeping setup in Desk forms with better descriptions; a top bar shell; renaming the DocTypes.

---

## History

- 2026-10-25: Initial set D1 to D16. App renamed from working name `upscape_sign` to `frappe_sign`. Compatibility widened from 16.50+ to all of v16 (D15).
- 2026-10-25: Golden rule 6 (CLAUDE.md) also allows `ignore_permissions` in `services/audit.py`, to insert Sign Events that no role may create.
- 2026-10-24: Doc review before Phase 0. D2: LGPL scope stated. D3: intermediate PDF rendered in `finish` under the row lock. D17 added. DESIGN, ARCHITECTURE, PLAN and CLAUDE.md updated to match.
- 2026-10-25: D10 changed after Gate 1 review: link tokens are derived from the site key, so reminders keep earlier links working; resend still rotates.
- 2026-10-25: D18 added after the Phase 2 pilot setup: plain-language staff app as the main surface (UX_PLAN.md decisions 1 to 5, confirmed by the user).
