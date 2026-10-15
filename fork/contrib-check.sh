#!/usr/bin/env bash
# Pre-PR checks reproducing the review rules found in upstream (.coderabbit.yaml, .pr_agent.toml,
# .cursor/rules/engineering-standards.md, helm/ARCHITECTURE.md, security-pip-auditing.yaml).
set -uo pipefail
mapfile -t FORK_ONLY < <(git show devel:fork/fork-only-paths | sed 's#/$##')
fail=0
err()  { echo "ERROR: $*"; fail=1; }
warn() { echo "WARN:  $*"; }

git fetch upstream --no-tags -q || err "cannot fetch upstream"
branch=$(git branch --show-current)
case "$branch" in main|devel) err "run from a feature branch, not $branch";; esac

git merge-base --is-ancestor upstream/main HEAD || err "branch is behind upstream/main (make contrib-update)"

changed=$(git diff --name-only upstream/main...HEAD)
for p in "${FORK_ONLY[@]}"; do
  echo "$changed" | grep -qE "^${p}(/|$)" && err "fork-only path in diff: $p"
done
[ -z "$changed" ] && err "no change against upstream/main"

added=$(git diff -U0 upstream/main...HEAD -- '*.py' | grep -E '^\+[^+]' || true)
echo "$added" | grep -nE 'TODO|FIXME|HACK' && err "TODO/FIXME/HACK added"
echo "$added" | grep -nE '^\+\s*except\s*:' && err "bare except added"
echo "$added" | grep -nE '^\+\s*print\(' && warn "print() added: use logging"

echo "$changed" | grep -q '^helm/' && warn "helm/ touched: bump Chart.yaml version, helm lint, helm template, helmfile diff"
echo "$changed" | grep -q '^\.github/workflows/' && warn ".github/workflows touched: pin action versions (no @main/@master)"

pyfiles=$(echo "$changed" | grep '\.py$' || true)
if [ -n "$pyfiles" ]; then
  if command -v ruff >/dev/null; then echo "$pyfiles" | xargs -r ruff check || err "ruff failed"; else warn "ruff not installed"; fi
fi
if command -v gitleaks >/dev/null; then gitleaks detect --log-opts "upstream/main..HEAD" --no-banner || err "gitleaks found secrets"; else warn "gitleaks not installed"; fi

echo "Reminders: type hints on all functions, pytest tests for new public functions, every error path logs,"
echo "  Conventional Commits (feat:/fix:), hexagonal layering, no secrets; run pip-audit on touched Python components."
exit $fail
