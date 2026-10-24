#!/usr/bin/env bash
# Refresh the vendored Frappe semgrep rules in .semgrep/frappe/ from frappe/semgrep-rules.
# Usage: scripts/update_frappe_semgrep_rules.sh [commit]   (default: tip of develop)
set -euo pipefail

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
ref="${1:-develop}"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

git clone --quiet https://github.com/frappe/semgrep-rules.git "$work/rules"
git -C "$work/rules" checkout --quiet "$ref"

target="$repo_root/.semgrep/frappe"
rm -rf "$target"
mkdir -p "$target/security"
cp "$work/rules/LICENSE" "$target/"
cp "$work/rules/rules/"*.yml "$target/"
cp "$work/rules/rules/security/"*.yml "$target/security/"

echo "Vendored frappe/semgrep-rules at $(git -C "$work/rules" rev-parse HEAD)"
echo "Update the commit in .semgrep/README.md."
