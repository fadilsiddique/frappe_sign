# Frappe Sign

E-signatures for Frappe and ERPNext v16. Send any document, usually from its Print Format, for signature. Signers sign by link on a phone or a computer, with an optional code by email or WhatsApp. The final PDF gets a PAdES-B-LT seal with a trusted timestamp and a certificate of completion, and is written back to the source document.

- Runs on every Frappe and ERPNext v16 release (v16.0.0 and later). ERPNext is optional.
- English and Arabic, right to left included.
- Company seal from a PKCS#12 file, a PKCS#11 token or HSM, or a Cloud Signature Consortium service.
- Hash-chained audit trail, public verify page, `bench frappe-sign verify`.

## Install

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app https://github.com/fadilsiddique/frappe_sign --branch main
bench --site <site> install-app frappe_sign
bench build --app frappe_sign
```

Then follow the [admin guide](docs/ADMIN_GUIDE.md): email account, seal, company profile, document types, template.

Needs Python 3.14, Node 24, MariaDB, Redis, and workers for the `default`, `short` and `long` queues.

## Documents

| | |
| --- | --- |
| [Admin guide](docs/ADMIN_GUIDE.md) | Setup in order, sending, reminders, WhatsApp, remote seals, health, troubleshooting |
| [Anchor guide](docs/ANCHOR_GUIDE.md) | Place signature boxes in a Print Format with `sign_field()` |
| [API reference](docs/API.md) | Whitelisted calls and error codes (generated) |
| [Changelog](CHANGELOG.md) | Release notes |
| [Security review](docs/SECURITY_REVIEW.md) | DESIGN section 5, control by control |
| [Load test](docs/LOAD_TEST.md) | 150-page PDF, 50 concurrent signers |
| [Design](docs/DESIGN.md), [decisions](docs/DECISIONS.md), [architecture](docs/ARCHITECTURE.md), [plan](docs/PLAN.md) | How it works and why |

## Develop

```bash
bench --site sign.localhost run-tests --app frappe_sign      # also run on a site without ERPNext
pre-commit run --all-files
cd frontend && yarn test && yarn typecheck && yarn lint
python3 scripts/make_api_docs.py                              # after changing api/
```

Read [CLAUDE.md](CLAUDE.md) for the rules this repository follows (layers, no commits in services, private files, no AGPL dependencies).

## License

MIT
