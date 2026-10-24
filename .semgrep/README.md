# Semgrep rules

- `rules/`: project rules that enforce the golden rules in `CLAUDE.md`. Each rule has test cases in `rules/frappe_sign.py`. Run them with `semgrep --test .semgrep/rules`.
- `frappe/`: rules from [frappe/semgrep-rules](https://github.com/frappe/semgrep-rules) (MIT, see `frappe/LICENSE`), vendored so that pre-commit and CI run the same rules offline.

Vendored commit: `81a6e3d47a328249e8ddf04c586e493dd5553002` (2026-09-30).

To update the vendored rules, run `scripts/update_frappe_semgrep_rules.sh`, check the diff, and update the commit above.
