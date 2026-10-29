# Frappe Sign: Manual QA checklists

Tick each item on a site with an outgoing Email Account and a Sign Profile with a sealing certificate. Items marked (auto) are also covered by the Playwright tests in `e2e/` (`yarn e2e` in `frontend/`, see `frontend/playwright.config.ts`).

## U.13: Quality pass

Screenshots are in `docs/ux/after/` (`u13-*`, with `-rtl` for right to left).

- [ ] (auto) Home, Sent, New request, Templates and Settings at 1440 and 390 px, left to right and right to left: no sideways scroll, no serious axe finding (WCAG A and AA, contrast included). `e2e/staff-qa.spec.ts`.
- [ ] (auto) Guest consent and signing screens, the expired screen and `/sign-verify` at 390 px, both directions: same checks. `e2e/guest-qa.spec.ts`.
- [ ] (auto) The first Tab shows a focus ring on every staff, guest and verify page.
- [ ] (auto) Guest bundle 94.7 KB gzipped (budget 250 KB): `yarn size`.
- [x] (auto) Stale browsers: the app shells and `/sign-verify` send no-cache headers, and every built asset has a content hash in its name, so an old cache cannot serve old code.
- [ ] Read the Arabic screens with a native reader once the translations land (P3.5). The right to left checks use English text with `dir="rtl"`, so they test layout, not wording.
- [ ] Screen reader pass on the signing page and the Sent list (the automated checks do not cover reading order).
- [ ] Gate 2.5 walk-through on a fresh site by someone who has not seen the app: under 15 minutes, no docs, no help.

## U.11: Verify page and branded emails

Use a Sign Profile with a logo and a brand color. Send a request to your own Gmail and Outlook web addresses.

- [ ] (auto) `/sign-verify`: a dropped PDF without a seal shows "Not sealed"; an unknown request ID shows "Nothing found"; nothing scrolls sideways at 390 px.
- [ ] A sealed PDF from a completed request shows "This document is genuine", the signers and the seal owner. The same PDF with one byte changed shows "Changed after signing".
- [ ] The invitation, reminder, completed and declined emails show the logo and company name on top, one button in the brand color, and the footer, in Gmail web and Outlook web.
- [ ] A light brand color (such as yellow) gets dark button text; a dark one gets white text.
- [ ] A Sign Profile with no logo and no color gives a plain dark button and no broken image.
- [ ] The logo file is public: a private logo shows as a broken image in the email (known limit).

## U.12: Desk touch points

- [ ] (auto) The send dialog has no checkbox column and no Kind column; the message sits behind "Add a message"; the second button reads "Preview and edit".
- [ ] (auto) A sent document's form shows "Signature: Sent", "waiting for <name>" and the request link.
- [ ] (auto) The Signatures workspace has shortcuts for Open Frappe Sign, New request, Settings and Get started. The sidebar lists Home, Requests, Templates, Triggers and Settings only.
- [ ] Sign Event, Sign Capture and other internal DocTypes are still found through the Desk search bar.

## P2.9: Send wizard with a Print Format source

- [ ] (auto) Quotation form, Send for Signature, Customize: `/sign/new` opens with the Quotation, the template and the Customer's contact filled in.
- [ ] (auto) Preview shows the rendered Print Format with a box per `sign_field()`, coloured by role; a role without a signer is flagged.
- [ ] Changing the template reloads the recipients, the preview and the prefilled values.
- [ ] A recipient not found on the document says "Not found on the document"; Send stays disabled until it is filled.
- [ ] A Print Format with a generator other than wkhtmltopdf or chrome shows the untested-generator warning.
- [ ] "From a document" on the first step works for a DocType typed by hand; choosing a Print Format template from the template list asks for the document.
- [ ] Prefilled values (template fields with a prefill path) are listed under "Filled from the document".
- [ ] (auto) Send opens the envelope detail.

## P2.5: Desk (Quotation)

Enable Quotation in Sign Settings (System Manager) and publish a Print Format template for it.

- [ ] (auto) Quotation form: "Send for Signature" opens a dialog with the template and the Customer's contact filled in.
- [ ] (auto) "Send" queues the envelope; it becomes Sent once the worker has rendered it.
- [ ] After sending, reload: the dashboard shows "Signature: Sent", and "Signature > Signature Envelope" opens `/sign/envelopes/<id>`.
- [ ] A Quotation whose Customer has no contact: the email cell is empty and "Send" asks for it.
- [ ] "Customize" opens `/sign/new` with the Quotation and template chosen.
- [ ] No template for the DocType: the button explains where to make one.
- [ ] (auto) Print view: "Send for Signature" appears for Quotation and not for a DocType that is not enabled; the envelope uses the Print Format and Letter Head on screen.
- [ ] (auto) List view: select rows, Actions, "Send for Signature"; a notification reports how many were sent and which were skipped.
- [ ] A user without Sign User or Sign Manager sees none of the buttons.
- [ ] Cancelled documents show no "Send for Signature" button.

## P1.17: Send wizard, envelope list and detail

### Send wizard (`/sign/new`)

- [ ] (auto) A published template appears under "From a template"; choosing it shows one row per role.
- [ ] (auto) Name and email for each recipient; "Send" stays disabled until every row is valid.
- [ ] "Upload a PDF" accepts a PDF, rejects an encrypted PDF with a readable message, and opens the Fields step.
- [ ] Fields step: roles added in the roles panel get their own colour; fields placed for each role keep that colour.
- [ ] Review: title, message, signing order and verification are saved on the envelope.
- [ ] (auto) After "Send" the envelope detail opens and shows "Sending", then "Sent" once the worker has run.
- [ ] With no outgoing Email Account, sending shows "Set up an outgoing Email Account" and the draft stays open with a Send button.

### Envelope list (`/sign/envelopes`)

- [ ] Filters: All, Waiting, Draft, Completed, Declined/voided/expired.
- [ ] A Sign User sees only envelopes they sent, receive or were shared; a Sign Manager sees all.
- [ ] Status badges: Sending, Send failed, Sent, In Progress, Sealing, Completed, Declined, Voided, Expired.

### Envelope detail (`/sign/envelopes/<id>`)

- [ ] (auto) Recipients with role, kind, email and status.
- [ ] (auto) Audit trail lists every event with time (system time zone), actor and IP; "Hash chain verified" is shown.
- [ ] Remind emails the same link again; the link in the first email still opens.
- [ ] "New link" replaces the link: the old one shows "Link not valid".
- [ ] "New link" on a recipient accepts a corrected email address.
- [ ] Void asks for a reason; signers who were invited get the cancellation email.
- [ ] After completion: Original PDF, Signed PDF and Certificate downloads work and are recorded as "Downloaded" events.
- [ ] "Retry seal" appears only when sealing failed, and only a Sign Manager can use it.
- [ ] The page refreshes by itself while the envelope is open or sealing.

### Home (`/sign`)

- [ ] Cards: Needs my signature, Waiting for others, Completed this month, Expiring in 3 days.
- [ ] "Sign now" opens the signing page for a company-side signer, with the same link as their email.

## P1.14: Guest signing on a phone

- [ ] (auto) 390 px wide: no horizontal scroll on consent, signing and done screens.
- [ ] (auto) "Start" / "Next field" jumps to the next required field and opens it.
- [ ] (auto) Draw a signature, save, finish; the same link then shows "Already signed".
- [ ] Type a signature in each script font, including an Arabic name in Aref Ruqaa.
- [ ] Upload a signature image (PNG, JPEG); a large or non-image file is refused with a message.
- [ ] Email verification: code arrives, a wrong code shows the attempts left, a new code waits 60 seconds.
- [ ] Decline with a reason; Delegate to another person (only when the template role allows it).
- [ ] Terminal screens: Link not valid, Not your turn (names the signer to wait for), Cancelled, Declined, Completed.

## Gate 1: Adobe Reader

- [ ] Trust `frappe_sign/tests/fixtures/certs/root_ca.pem` in Adobe Reader (Preferences, Signatures, Identities and Trusted Certificates, More, Trusted Certificates, Import).
- [ ] Open `tests/output/sample_signed.pdf`: the signature panel shows a valid signature by "Frappe Sign Test Seal", the document has not been modified since it was signed, and the signature includes an embedded timestamp.
- [ ] The signature is LTV enabled (revocation data embedded).
- [ ] The certificate of completion pages list the signers, hashes and audit trail; the QR code opens `/sign-verify`.
