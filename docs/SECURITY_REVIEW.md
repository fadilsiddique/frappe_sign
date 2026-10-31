# Security review of DESIGN section 5 (P3.8)

Reviewed on 2026-10-29 against the code at the commit that adds this file. Every control of DESIGN 5.1 to 5.7 is listed once, with the test that proves it. A control is **Implemented and tested**, **Fixed in P3.8** (a gap found by this review, now closed and tested), or **Gap** (tracked, with the reason it is not closed). Test names are in `frappe_sign/tests/`.

## Summary

57 controls were reviewed.

| Result | Count |
| --- | --- |
| Implemented and tested | 47 |
| Implemented, no test (the access log note: documentation only) | 1 |
| Fixed in P3.8 (3 were real defects, 5 only lacked a test) | 8 |
| Gap, tracked | 1 |

Besides the matrix, 3 risks are tracked (open items 2 to 4).

Fixed in P3.8:

1. **Parallel signers forked the audit chain or failed.** `audit.append` read the last event from a stale snapshot, and most guest entry points had no conflict retry. 6 signers opening one envelope together gave `Duplicate entry ... unique_envelope_seq`; in the 50 signer load test 40 requests failed. Now the envelope lock is taken before any consistent read, the last event is read with a locking read, and every entry point that appends retries. Tests: `test_concurrency.TestParallelOpens`; load test in `LOAD_TEST.md`.
2. **Public verification opened the seal.** `verify.trust_context` decrypted the certificate password (and would have logged in to an HSM) on an anonymous request, against 5.3 "decrypted material exists only inside the seal job". The company's public chain is now stored on the Sign Certificate and verification reads only that. Tests: `test_verify_trust`.
3. **Every leaf certificate was a trust root.** asn1crypto's `Certificate.self_signed` is the text `"no"`, `"maybe"` or `"yes"`, so `if cert.self_signed` was always true. Verification and the seal's validation context trusted the sealing leaf as if it were a root. Now only self-signed certificates count. Tests: `test_seal.TestOwnRoots`, `test_verify_trust`.
4. **Missing tests** for controls that were implemented: no role may create a Sign Event, a Sign Manager may only select a Sign Certificate, the public verify page is rate limited and reveals nothing for an unknown ID, the Consented event carries the disclosure version. Tests: `security/test_review.py`.

Gaps, tracked: see "Open items" at the end.

## 5.1 Signer journey

| Control | Status | Evidence |
| --- | --- | --- |
| Send freezes and hashes the PDF, creates recipients and tokens, writes `Sent`, emails the link | Implemented and tested | `test_envelope_service.TestSend.test_render_freezes_the_pdf_and_invites_the_first_signer` |
| Open: token hashed and looked up; status, expiry and routing checked; unknown and expired tokens look the same | Implemented and tested | `test_signing_service.TestOpen.test_unknown_and_expired_tokens`, `test_voided_envelope_is_not_open` |
| Sequential signer sees "Waiting for X" | Implemented and tested | `TestOpen.test_sequential_signer_waits_for_their_turn` |
| `Viewed` event written when the session opens | Implemented and tested | `TestOpen.test_open_without_otp_gives_a_session_and_a_scoped_summary` |
| OTP: 6 digits, stored hashed, validity, 5 attempts per code, 60 s cooldown | Implemented and tested | `TestOtp` (`test_email_otp_flow`, `test_five_wrong_codes_lock_the_code`, `test_expired_code`, `test_resend_cooldown`), `test_integrity.TestHashedSecrets.test_session_secret_and_otp_are_stored_hashed` |
| An unverified Sign Session holds the OTP hash; success sets `verified_on` and issues the secret | Implemented and tested | `TestOtp.test_email_otp_flow` |
| OTP over WhatsApp uses the same limits | Implemented and tested | `test_whatsapp.TestWhatsappOtp` |
| Consent first; `consent_version` recorded in event `Consented` | Fixed in P3.8 (test added) | `TestFields.test_consent_comes_first`, `test_review.TestConsentIsRecorded` |
| Fields validated on the server (type, required, regex, options) | Implemented and tested | `TestFields.test_values_are_validated_on_the_server`, `test_captures_are_checked_and_stored_privately` |
| Decline needs a reason; delegate only if the role allows | Implemented and tested | `TestDeclineAndDelegate` |
| Finish takes the envelope row lock, re-validates required fields, renders the intermediate PDF in the request, stores its hash on the recipient and in event `Signed` | Implemented and tested | `TestFinish.test_sequential_flow_renders_intermediates_and_queues_one_seal`, `test_concurrency.test_parallel_finishes_queue_one_seal` |
| Notifies the next routing group | Implemented and tested | `TestFinish.test_sequential_flow_...` |
| Last signer triggers sealing; after `Sealed` everyone gets the PDF and `envelope_completed` is published | Implemented and tested | `test_sealing.test_seal_job_completes_the_envelope`, `test_events` |
| Company-side signers use the same link and flow | Implemented and tested | `test_staff_permissions.test_my_signing_link_for_a_company_signer` |
| A logged-in user whose email matches is offered their Sign Saved Signatures | **Gap** | The DocType exists, nothing offers it in the guest app. Convenience, not a security control. Tracked (item 1). |

## 5.2 Guest access controls

| Control | Status | Evidence |
| --- | --- | --- |
| Token is an HMAC of recipient row and version under the site key; only its SHA-256 is stored | Implemented and tested | `test_hashing.TestDeriveToken`, `test_integrity.TestHashedSecrets.test_recipient_token_is_stored_hashed` |
| Reminders re-derive the same link; resend raises `token_version` and ends open sessions | Implemented and tested | `TestOpen.test_reminders_keep_the_link_and_resend_replaces_it`, `test_guest_api.TestScoping.test_token_reuse_after_resend_is_denied`, `test_resend_ends_open_sessions` |
| 32 byte session secret, only its hash stored, sent in `X-Sign-Session`, never a cookie | Implemented and tested | `test_guest_api.test_pdf_is_streamed_privately` (no `Set-Cookie`), `test_integrity.TestHashedSecrets` |
| Session: 30 min idle, 24 h absolute | Implemented and tested | `TestSession.test_invalid_idle_and_expired_sessions`, `test_using_a_session_keeps_it_alive` |
| Rate limits: `open` 30/min, `verify_otp` 10/10 min, `save_*` 120/min, `request_otp` 5/hour per recipient | Implemented and tested | `test_guest_api.TestRateLimits` |
| Every guest endpoint is POST only, guest, rate limited | Implemented and tested | `test_guest_api.TestEndpoints.test_every_endpoint_is_post_only_guest_and_rate_limited` |
| Responses are recipient scoped: no source document name, no other recipients' emails; only own fields editable | Implemented and tested | `TestOpen.test_open_without_otp_gives_a_session_and_a_scoped_summary`, `test_guest_api.TestScoping` |
| One session cannot touch another envelope | Implemented and tested | `TestScoping.test_a_session_cannot_touch_another_envelope` |
| `ignore_permissions` only in `signing.py` after a session check, and in `audit.py`; each with a comment | Implemented and tested | Semgrep rule `frappe-sign-ignore-permissions` and its test cases (`.semgrep/rules/frappe_sign.py`), run by pre-commit and CI |
| PDF streams with `Cache-Control: no-store`, `Content-Disposition: inline`, no cookie | Implemented and tested | `test_guest_api.test_pdf_is_streamed_privately` |
| `get_pdf` serves the latest intermediate PDF, or the original | Implemented and tested | `test_signing_service.TestFinish` |
| `Referrer-Policy: no-referrer` on guest pages and API | Implemented and tested | `test_www.TestShellContext.test_guest_headers` |
| The token is in the URL, so access logs hold it; the guide says so | Implemented | `ADMIN_GUIDE.md`, "Security notes". Accepted residual risk, limited by expiry, rotation on resend and the OTP option. |
| A guest page has no CSRF surface; a logged-in signer gets a CSRF token | Implemented and tested | `test_www.test_guest_boot_has_no_csrf_token_or_user`, `test_logged_in_signer_gets_a_csrf_token` |
| Guest and portal calls cannot reach audit rows of other envelopes | Implemented and tested | `test_portal.TestDownload.test_someone_else_gets_a_permission_error_for_a_real_and_a_made_up_name` |

## 5.3 Cryptography

| Control | Status | Evidence |
| --- | --- | --- |
| One sealing certificate per Company, password through `get_password` | Implemented and tested | `test_certificate_service`, `test_sign_certificate` |
| Decrypted material exists only inside the seal job | **Fixed in P3.8** | `verify.trust_context` no longer decrypts; `test_verify_trust.test_verify_trust_never_decrypts_or_opens_the_signer` |
| Sign Manager can select a certificate but not read it | Fixed in P3.8 (test added) | `test_review.test_a_sign_manager_may_only_select_a_sign_certificate` |
| PIN, token and password are Password fields; a PIN pasted into the remote JSON is refused | Implemented and tested | `test_review.test_certificate_secret_fields_are_passwords`, `test_remote_signer.TestConfig.test_unknown_keys_are_refused`, `test_remote_certificate.test_the_pin_is_stored_encrypted_and_never_in_the_config` |
| Key present and certificate valid before each seal | Implemented and tested | `test_seal.test_unusable_certificate_raises_seal_error`, `test_remote_signer.TestValidityWindow` |
| TSA: URLs tried in order, first granted response wins, 10 s timeout, defaults when empty | Implemented and tested | `test_crypto.TestTimestamps` |
| Remote keys (PKCS#11, CSC) sign without the key leaving the HSM or service; errors never show the PIN | Implemented and tested | `test_remote_signer.TestPkcs11`, `TestCsc` (SoftHSM and a fake CSC service) |
| A PKCS#11 library path is loaded into the worker; a site may restrict the list | Implemented and tested | `test_remote_certificate.test_the_site_can_limit_the_libraries`, `test_remote_signer.TestConfig` |
| Only self-signed certificates become trust roots | **Fixed in P3.8** | `test_seal.TestOwnRoots`, `test_verify_trust` |

## 5.4 Sealing

| Control | Status | Evidence |
| --- | --- | --- |
| Queued under the row lock with a deduplicated job id | Implemented and tested | `test_concurrency.test_parallel_finishes_queue_one_seal` |
| Exactly one seal when two jobs run | Implemented and tested | `test_concurrency.test_two_seal_jobs_seal_once`, `test_sealing.test_second_job_does_nothing` |
| Failure sets `Failed`, retries after 1, 5, 30 minutes, alerts the sender after the last | Implemented and tested | `test_sealing.test_failures_retry_with_backoff_then_alert` |
| `retry_seal` only for a Sign Manager and only after `Failed` | Implemented and tested | `test_sealing.test_retry_seal_is_for_sign_managers_after_failure` |
| Snapshot conflicts retried | **Fixed in P3.8** | `test_audit.TestRetryOnConflict`, `test_concurrency.TestParallelOpens`, load test (50 of 50 signers) |

## 5.5 Audit chain

| Control | Status | Evidence |
| --- | --- | --- |
| `hash = sha256(prev_hash + canonical JSON)`; first event from the envelope name | Implemented and tested | `test_audit.test_events_chain_from_the_envelope_name` |
| Hashed fields, UTC with microseconds | Implemented and tested | `test_audit.test_at_is_utc_with_microseconds`, `test_tampered_field_is_found`, `test_tampered_payload_is_found` |
| `seq` assigned under the row lock, no gap or fork | Implemented and tested | `test_audit.test_seq_is_assigned_under_the_envelope_row_lock`, `test_forked_seq_is_refused_by_the_database`, `TestParallelOpens` |
| No role has create permission on Sign Event | Fixed in P3.8 (test added) | `test_review.test_no_role_may_create_a_sign_event`; write and delete: `test_integrity.test_no_role_may_write_or_delete` |
| Events cannot be changed or deleted | Implemented and tested | `test_integrity.TestInsertOnlyRecords` |
| A rewritten or deleted event is found | Implemented and tested | `test_audit.test_rewritten_event_with_fresh_hash_breaks_the_next_link`, `test_deleted_event_is_found` |
| `audit_head` written at completion and printed on the certificate | Implemented and tested | `test_sealing.test_seal_job_completes_the_envelope` |
| `bench frappe-sign verify` reports the first bad event | Implemented and tested | `test_verify_command` |

## 5.6 Verify page

| Control | Status | Evidence |
| --- | --- | --- |
| SHA-256 checked against `signed_sha256`, seal validated with pyHanko | Implemented and tested | `test_staff_permissions.test_public_verify_by_file_and_by_id` |
| No document content for anonymous users; an ID alone reveals no signer | Implemented and tested | same test, `test_review.TestPublicVerifyIsRateLimited` |
| Rate limited (10 per minute per IP) | Fixed in P3.8 (test added) | `test_review.TestPublicVerifyIsRateLimited.test_ten_a_minute_per_ip` |
| Prefilled ID is escaped | Implemented and tested | `test_www.TestVerifyPage.test_prefill_is_escaped` |
| Uploads capped at 25 MB | Fixed in P3.8 (test added) | `test_review.TestPublicUploadCap` |

## 5.7 Legal note

Not a control. The note is in DESIGN and the admin guide; counsel decides the level a contract needs.

## Other checks made in this review

- **Secrets in logs.** Frappe's `log_error` adds local variables to the Error Log only when `developer_mode` is on, and masks names containing `password`, `secret`, `token` or `key`. In developer mode an OTP held in a variable named `code` is shown. Production sites do not turn developer mode on. Tracked as item 2.
- **Dependency audit.** `pip-audit` on the bench environment and `yarn audit` on `frontend/`. See "Dependency findings".
- **Remote signing.** A System Manager can point a PKCS#11 certificate at any library path; the optional `frappe_sign_pkcs11_modules` list in `site_config.json` restricts it. CSC needs https (or loopback).
- **WhatsApp.** Messages go through frappe_whatsapp's own document, inserted with `ignore_permissions` only inside `signing.py` for the guest OTP; staff invitations use the sender's permissions. A site must give the sender's role create permission on WhatsApp Message, or the invitation falls back to email only and the sender is told.

## Dependency findings

`pip-audit` against the bench environment (Frappe at the `version-16` head) lists advisories in packages that Frappe pins, not in frappe_sign's own:

| Package | Installed | Fixed in | Used by frappe_sign for untrusted input? |
| --- | --- | --- | --- |
| pypdf | 6.15.0 (22 advisories) | 6.21.2 | Yes: staff uploads, the public verify upload, guest attachments. Frappe pins `pypdf==6.15.0` here and `==6.6.0` at v16.0.0. |
| Pillow | 12.3.0 (39 advisories) | 13.0.0 | Yes: signature and attachment images, logos. Frappe pins `~=12.3`. |
| Werkzeug | 3.1.6 | 3.1.9 | Frappe's web server. |
| weasyprint | 68.0 | 70.0 | No (Frappe's own PDF engine option). |

`yarn audit` for `frontend/`: one moderate advisory in `postcss-selector-parser` (a build-time dependency of frappe-ui through `@tailwindcss/typography`); it is not in any shipped bundle. Root `yarn audit`: none.

These are tracked, not fixed here: frappe_sign's ranges (`pypdf>=6.6.0,<7`) already allow the fixed versions, but Frappe's own pins decide what a site runs. The mitigations in the code are the page cap, the upload size cap, the PDF sanitizer, the image size and pixel caps (`MAX_IMAGE_SIDE`), the 25 MB cap and the rate limit on the public verify upload. See item 3.

## Open items

1. **Saved signatures in the guest app (5.1, last paragraph).** Not built: no API or screen offers a logged-in signer their Sign Saved Signatures. Not a security control. Decision for the owner: build it in 1.1, or remove the sentence from DESIGN. Release notes list it as not in 1.0.
2. **Variables in Error Log under developer mode.** An OTP in a local named `code` shows in a developer-mode Error Log. Production is unaffected. Rename or wrap the variable in a later release; no action needed for v1.0.
3. **Vulnerable pinned dependencies (pypdf, Pillow).** Deploy v1.0 on a Frappe release that pins pypdf 6.21.2 or newer and Pillow 13 or newer when Frappe publishes it. Until then the verify upload and guest images are the exposed surface. Re-run `pip-audit` before every release.
4. **OTP attempt counter lives in Redis (5.1 step 3).** It is in the cache because a failed request rolls back the database. A cache flush resets the count for a live code. An attacker cannot flush it; the 10 minute code life, the 10 per 10 minutes limit and the 6 digit space still hold. Accepted for v1.0.
