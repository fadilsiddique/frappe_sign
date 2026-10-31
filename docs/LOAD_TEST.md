# Load test (P3.8)

A 150-page PDF and 50 concurrent signers, measured on 2026-10-29. The script is `frappe_sign/tests/loadtest.py`; it refuses to run unless the site has `allow_tests`, and it deletes everything it creates.

```bash
# from the bench directory; heavy=1 uses a generated 150-page, 15.7 MB PDF with a photo on every page
bench --site sign.localhost execute frappe_sign.tests.loadtest.run --kwargs '{"workers": 4, "signers": 50, "heavy": 1}'
```

## What was measured

| | |
| --- | --- |
| Machine | Apple M2, 8 cores, 8 GB, MariaDB 11.8 on the same machine, Python 3.14.7 |
| PDFs | `light`: the fixture `many_pages_150.pdf` (150 text pages, 75 KB). `heavy`: generated, 150 pages, 15.7 MB (the 20 MB upload limit is the ceiling) |
| Workers | Separate processes, each with its own Frappe connection, standing in for gunicorn workers. 4 is the default shape of a small production bench; 8 matches the core count |
| Requests | open, consent, one signature, finish: the calls a signer's browser makes. All 50 start at once; latency counts from that moment, so it includes waiting for a free worker |
| Left out | The network (timestamp servers and revocation lookups), email delivery, the browser. The seal uses the offline test timestamper, so the seal time is CPU only. In the Gate 2 browser test, sealing through the public TSA took about 35 s |

Phases:

1. **One envelope, two signers, then the seal.** Cost of one signer and of the seal job.
2. **50 envelopes, one signer each, at once.** Many documents in parallel.
3. **One envelope with 50 parallel signers, all finishing at once.** The worst case for D3 (the intermediate PDF is rendered in the request, under the envelope row lock): the 50 renders must go one after the other.

## Results

Times are seconds; memory is peak resident memory of the worker process in MB. Errors were zero in every run below.

### 1. One envelope (single worker process)

| | light | heavy |
| --- | --- | --- |
| Create and send (draft, freeze the PDF, invite) | 0.45 | 0.52 |
| First signer: open, consent, capture, finish | 0.67 (finish 0.36) | 0.70 (finish 0.38) |
| Last signer: finish | 0.07 | 0.16 |
| Seal job (overlay, certificate pages, PAdES-B-LT, store) | 2.2 | 2.2 |
| Peak memory after signing | 190 | 281 |
| Peak memory after the seal | 195 | 331 |

### 2. 50 envelopes at once, one signer each

| | light, 4 workers | heavy, 4 workers | heavy, 8 workers |
| --- | --- | --- | --- |
| All 50 done after | 4.1 | 7.9 | 7.8 |
| Request latency p50 / p95 / max | 2.5 / 3.9 / 4.1 | 5.4 / 7.9 / 7.9 | 5.1 / 7.7 / 7.8 |
| `finish` p50 / p95 / max | 0.16 / 0.57 / 0.58 | 0.32 / 0.82 / 1.51 | 0.57 / 1.27 / 2.74 |
| Peak worker memory | 200 | 273 | 211 |

### 3. One envelope, 50 signers finishing at once

| | light, 4 workers | heavy, 4 workers | heavy, 8 workers |
| --- | --- | --- | --- |
| Signed | 50 of 50 | 50 of 50 | 50 of 50 |
| Seal jobs queued | 1 | 1 | 1 |
| All 50 done after | 10.1 | 15.9 | 19.4 |
| Request latency p50 / p95 / max | 5.0 / 9.7 / 10.1 | 8.0 / 15.1 / 15.9 | 9.3 / 18.5 / 19.3 |
| `finish` p50 / p95 / max (the render under the lock) | 0.14 / 0.17 / 0.17 | 0.24 / 0.30 / 0.37 | 0.26 / 0.39 / 0.61 |
| Peak worker memory | 185 | 324 | 268 |

## What it found

Before this test, phase 3 did not work. With 50 signers on one envelope, 17 to 48 requests failed, depending on timing:

- `Duplicate entry '<envelope>-<n>' for key 'unique_envelope_seq'`: two requests that had both waited for the envelope lock read the same last audit event from an old snapshot and tried to write the same sequence number. The database refused the second, so the audit chain stayed whole, but the signer saw an error.
- `QueryDeadlockError 1020, Record has changed since last read`: the conflict retry that protected `finish` was missing from `open`, `consent`, `save_fields`, `save_capture` and the OTP calls, and three attempts were not enough under contention.

Fix (DESIGN 5.4): every guest call that appends an event takes the envelope row lock before it reads anything else, the last event is read with a locking read, and all the entry points retry on a snapshot conflict (five attempts, short uneven pause). Tests: `test_concurrency.TestParallelOpens` (6 signers opening together) and the runs above.

## Reading the numbers

- **D3 holds.** Rendering the intermediate PDF inside `finish`, under the row lock, costs 0.07 to 0.38 s for 150 pages (0.61 s worst case with 8 workers fighting for 8 cores). Fifty signers on one envelope wait for each other, and the last one is done after 16 to 19 s, far below a 120 s web timeout. No change to D3 is proposed.
- **A signer's own work is under one second** (open 0.26, capture 0.05, finish 0.38 on the heavy PDF), measured without queueing.
- **Memory.** One web worker peaks at about 270 to 325 MB when it renders a 15 MB, 150-page PDF, and at about 190 to 200 MB on the text-only PDF. The seal job peaks at about 330 MB. Five long-queue jobs sealing together would need about 1.7 GB; size the worker host for that, or run fewer seal workers.
- **More workers than cores do not help.** With 8 workers on 8 cores, phases 2 and 3 were no faster and `finish` was slower, because the cores and MariaDB were already busy.
- **Not tested:** a production database host apart from the app, networked Redis, real TSA latency (add up to 35 s to a seal; it runs in a job, not in a request), and PDFs whose pages are far larger than 100 KB (the 20 MB upload limit bounds this).
