# Changelog

## 1.0.0 (release notes, not yet tagged)

First release. Frappe v16.0.0 and later; ERPNext v16 optional.

### What you can do

- Send any document for signature from its form, its print view, a list (up to 100 at once), a template, or automatically (triggers on submit, save, workflow state, value change or a date).
- Place signature, initials, name, date, text, number, checkbox, dropdown, attachment and company stamp fields in a designer, or with `sign_field()` in a Print Format.
- Signers sign by link on a phone: draw, type or upload a signature, with an optional code by email or WhatsApp. They can decline or pass the document on.
- Sequential or parallel signing, approvers, company-side signers on the same link.
- The final PDF is sealed once (PAdES-B-LT, RFC 3161 timestamp) with a certificate of completion, attached to the source document, with its signature status updated. A next step can run: submit, workflow action, create a mapped document, set a field, call a method.
- Anyone can check a PDF at `/sign-verify`. `bench --site <site> frappe-sign verify <request>` checks the audit chain and file hashes.
- Reminders, expiry, certificate expiry warnings and date triggers run on the scheduler.
- Staff app at `/sign` in plain words: Home with setup steps, Sent, request detail, send wizard, templates, designer, Settings, Health.
- English and Arabic, right to left, with Arabic emails. A request has its own language; a signer can switch.
- "My signed documents" at `/my-signatures` for signers with an account.
- The company seal can be a PKCS#12 file, a PKCS#11 token or HSM (tested with SoftHSM), or a CSC service.

### Fixed during hardening (found by the security review and the load test)

- 50 signers finishing or opening one request at once forked the audit sequence or failed. All 50 now sign (`docs/LOAD_TEST.md`).
- Public verification no longer opens the sealing key or password. It uses the certificates stored on the Sign Certificate.
- A signer's own certificate was trusted as if it were a root. Only self-signed certificates are trust roots now.

### Numbers

| | |
| --- | --- |
| 150-page, 15.7 MB PDF, one signer | 0.7 s from open to finish |
| Seal job (without network) | 2.2 s, 330 MB peak memory |
| 50 signers on one request, 4 workers | all done in 16 s, no errors |
| 50 requests at once, 4 workers | all done in 8 s, no errors |

Measured on an Apple M2 with 8 cores. See `docs/LOAD_TEST.md`.

### Needs a human before you rely on it

- Four pilot weeks without a lost or unsealed request (Gate 3).
- Open an HSM-sealed PDF in Adobe Reader. Only the offline test PKI and SoftHSM were checked.
- Review the Arabic screens (`docs/ux/ar/`) and the Arabic wording.
- WhatsApp messages to numbers that have not written to you need a Meta-approved template in frappe_whatsapp.

### Known limits

- Saved signatures are not offered to a logged-in signer yet (DESIGN 5.1, last paragraph).
- The Frappe release you deploy on decides the versions of pypdf and Pillow. Both have published advisories in the versions Frappe v16 pins today. Use a Frappe release that pins the fixed versions when it exists (`docs/SECURITY_REVIEW.md`).
- The wrong-code counter for email and WhatsApp codes lives in Redis.
- Qualified signatures (UAE PASS), in-person signing and archival timestamps are for a later release.

### Upgrading

Run `bench migrate`, then restart the web server and all workers. A patch stores the public certificate chain of existing seals. Run `bench build --app frappe_sign` so Desk gets the new script.
