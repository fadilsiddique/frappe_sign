# Frappe Sign: Architecture

`frappe_sign` is an e-signature app for Frappe and ERPNext v16 (all minors, see D15). Any document can be sent for signature from its own Print Format, signed by external parties via link, sealed with a PAdES signature, and written back to the source document.

Five layers, one rule: clients only talk to thin APIs, APIs only call services, and services are the single home for business logic. PDF work, ERPNext specifics and slow tasks are delegated to workers and adapters.

## Layers

```mermaid
flowchart TB
    subgraph Clients
        A1["Staff app /sign<br/>Vue + frappe-ui SPA"]
        A2["Guest signing /s/:token<br/>mobile-first"]
        A3["ERPNext Desk<br/>form, print, list buttons"]
        A4["Verify page /sign-verify<br/>public"]
    end
    subgraph API["API (thin, type-annotated)"]
        B1["api.staff<br/>logged in, Frappe permissions"]
        B2["api.guest<br/>token + OTP, rate limited"]
        B3["api.public<br/>verify only"]
    end
    subgraph Services["Services: all business logic"]
        C1[envelope] --- C2[signing] --- C3[template]
        C4[trigger] --- C5[audit] --- C6[notify]
        C7[writeback] --- C8[actions]
    end
    subgraph Workers["Workers and adapters"]
        D1["pdf/<br/>source, sanitize, anchors,<br/>overlay, certificate, seal"]
        D2["erpnext/<br/>resolvers, dashboards,<br/>field setup"]
        D3["jobs/ (RQ)<br/>render, seal, reminders,<br/>triggers, bulk"]
        D4["crypto/<br/>Signer, TSA"]
    end
    subgraph External["Storage and external"]
        E1[(MariaDB)]
        E2[(Private Files)]
        E3[Sealing cert<br/>p12 or HSM]
        E4[TSA RFC 3161]
        E5[Email / WhatsApp]
    end
    A1 & A3 --> B1
    A2 --> B2
    A4 --> B3
    B1 & B2 & B3 --> Services
    Services --> D1 & D2 & D3
    D1 --> D4
    D4 --> E3 & E4
    Services --> E1 & E2
    C6 --> E5
```

### Layer rules

| Layer | May import | Must not |
| --- | --- | --- |
| `api/` | `services/`, `utils/` | Contain business rules, call `frappe.db.commit()` |
| `services/` | `pdf/`, `crypto/`, `utils/`, DocType classes, `frappe` | Import from `erpnext` directly; commit transactions |
| `pdf/` | `pypdf`, `reportlab`, `pyhanko`, `pdf/types.py` | Import `frappe`, except `source.py` and `certificate.py`. Raise `exceptions.py` errors (raise `PdfError` subclasses from `pdf/types.py`, which services translate) |
| `crypto/` | `pyhanko`, `cryptography` | Touch DocTypes (receives decrypted material from services) |
| `erpnext/` | `services/`, `erpnext` (guarded) | Be imported by core code; only loaded via hooks registry when ERPNext is installed |
| `jobs/` | `services/` | Hold logic; they are transaction boundaries only. Every enqueued function is a `jobs/` entry point; services are never enqueued directly |
| DocType controllers | `utils/`, `exceptions`, `compat`, `crypto/pkcs12.py` | Hold business logic beyond validation and state guards |
| `jinja/` | `pdf/anchors.py`, `pdf/source.py`, `utils/` | Hold logic beyond writing the anchor markup; the marker format lives in `pdf/anchors.py` only |
| `utils/`, `exceptions.py`, `compat.py` | `frappe`, each other (`utils/` raises `exceptions.py` errors) | Import any other app layer; any layer except `pdf/` and `crypto/` may import them |

## Request flow: a customer signs a Quotation

```mermaid
sequenceDiagram
    autonumber
    actor S as Sales user
    participant D as Desk (desk.js)
    participant API as api.staff / api.guest
    participant SV as Services
    participant J as Jobs
    participant P as pdf/ + crypto/
    participant E as erpnext/ adapter
    actor C as Customer

    S->>D: Send for Signature
    D->>API: resolve_recipients, create_envelope, send_envelope
    API->>SV: envelope.send()
    SV->>J: enqueue render (after commit)
    J->>P: get_print -> sanitize -> find_anchors
    J->>SV: store original + SHA-256, issue tokens, event Sent
    SV-->>C: email / WhatsApp link /s/token
    C->>API: open(token), request_otp, verify_otp
    API->>SV: signing.open / verify
    C->>API: save_fields, save_capture, finish
    API->>SV: signing.finish (lock row, intermediate PDF + hash, event Signed)
    SV->>J: last signer? enqueue seal (job_id dedupe)
    J->>P: overlay -> certificate -> seal (PAdES-B-LT + TSA)
    J->>SV: store signed file, event Completed, publish envelope_completed
    SV->>J: enqueue one job per event handler (after commit)
    J->>SV: write-back: attach PDF, set sign_status, timeline
    J->>SV: post-sign action as sender
    SV->>E: Create Mapped Document uses ERPNext mapper
    E->>E: draft Sales Order
```

## Repository layout

```text
frappe_sign/
├── CLAUDE.md                     Instructions for Claude Code
├── docs/                         ARCHITECTURE, DESIGN, DECISIONS, PLAN
├── frontend/                     Vite project
│   ├── src/staff/                staff app entry, routes, pages
│   ├── src/guest/                guest signing entry, pages
│   ├── src/shared/               pdf viewer, field components, composables, api client, types
│   └── tests/                    Vitest
├── e2e/                          Playwright
├── package.json                  root "build" delegates to frontend/
├── pyproject.toml
└── frappe_sign/
    ├── hooks.py                  routes, jinja, doc_events "*", scheduler, frappe_sign_* hooks
    ├── compat.py                 feature-detected shims for anything newer than v16.0.0
    ├── frappe_sign/doctype/      17 DocTypes (module "Frappe Sign")
    ├── api/                      staff.py, guest.py, public.py
    ├── services/                 envelope.py, signing.py, template.py, trigger.py, audit.py, notify.py, events.py, writeback.py, actions.py
    ├── pdf/                      types.py, source.py, sanitize.py, anchors.py, overlay.py, certificate.py, seal.py, fonts/
    ├── crypto/                   signer.py (Signer, Pkcs12Signer, RemoteSigner), pkcs12.py (inspect only), tsa.py
    ├── erpnext/                  resolvers/, dashboards.py, setup.py (custom fields, Link Company)
    ├── jobs/                     render.py, seal.py, events.py, actions.py, bulk.py, reminders.py, triggers.py, housekeeping.py
    ├── utils/                    small shared helpers (hashing, dates, paths)
    ├── jinja/                    sign_field() anchor helper
    ├── exceptions.py             domain errors with HTTP codes and stable codes
    ├── public/js/desk.js         form, print view and list view integration
    ├── public/frontend/          build output (gitignored)
    ├── templates/                certificate.html, emails/
    ├── www/                      sign.html/.py, s.html/.py, sign-verify.html/.py
    ├── commands/                 bench frappe-sign verify
    ├── patches/
    └── tests/                    unit/, integration/, erpnext/, security/, fixtures/pdfs/
```

## Runtime topology

- **Web workers** serve the SPA shells, API and PDF streams.
- **RQ queues:**
  - `default`: render and send, event handlers, post-sign actions, trigger dispatch.
  - `long`: seal (TSA network call), bulk send.
  - `short`: notifications.
- **Scheduler:** reminders and expiry every 15 minutes; certificate warnings, session purge and date triggers daily.
- **Redis:** rate limiter counters, trigger DocType cache, job deduplication.
- **Realtime (socket.io):** envelope status updates to the staff app.

## Extension points

| Hook in `hooks.py` | Purpose |
| --- | --- |
| `frappe_sign_resolvers` | Map a DocType to a resolver that returns suggested recipients |
| `frappe_sign_events` | Subscribe handlers to domain events (`envelope_sent`, `recipient_viewed`, `recipient_signed`, `envelope_declined`, `envelope_voided`, `envelope_completed`) |
| `frappe_sign_post_sign_actions` | Register extra post-sign action types |

Other apps declare these in their own `hooks.py`; `frappe.get_hooks()` merges them.

## Compatibility (D15)

- Frappe and ERPNext `>=16.0.0,<17.0.0`. Floor APIs verified against the `v16.0.0` tag.
- Python `>=3.14,<3.15`, Node `>=24`.
- Newer APIs only via `compat.py` with feature detection.
- CI matrix: `v16.0.0` floor and `version-16` head, each with and without ERPNext.
- Print Formats using either `wkhtmltopdf` or `chrome` generator are supported and tested. Generators added after v16.0.0 (Typst, WeasyPrint) render, but anchors are not tested for them, and the send wizard shows a warning.