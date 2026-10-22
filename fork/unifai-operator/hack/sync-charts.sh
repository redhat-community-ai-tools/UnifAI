#!/usr/bin/env bash
# Copies the upstream charts and values deployed by UnifaiStack into internal/stack/assets (embedded in the binary).
# Upstream files are copied verbatim: every fork-specific setting (images, storage classes, URLs, resources) is applied
# by the operator at render time (internal/stack), never by editing charts. Run from fork/unifai-operator: `make charts`.
# `--check` copies into a temporary directory and fails when the embedded assets differ from upstream (`make charts-check`).
set -euo pipefail
check=
if [ "${1:-}" = --check ]; then check=1; shift; fi
src=${1:-../../helm}
assets=internal/stack/assets
dst=$assets
if [ -n "$check" ]; then
  tmp=$(mktemp -d)
  trap 'rm -rf "$tmp"' EXIT
  dst=$tmp/assets
fi
charts=(
  shared-resources/mongodb shared-resources/qdrant shared-resources/rabbitmq shared-resources/redis
  shared-resources/redis-insight shared-resources/temporal shared-resources/logging shared-resources/identity
  shared-resources/docling
  rag/unifai-rag-shared-storage rag/unifai-rag-server rag/unifai-rag-celery
  multiagent/unifai-multiagent-shared-storage multiagent/be multiagent/temporal-worker
  backend/unifai-backend ui
)
rm -rf "$dst"
mkdir -p "$dst/charts" "$dst/values"
for c in "${charts[@]}"; do
  out="$dst/charts/$(basename "$c")"
  cp -r "$src/$c" "$out"
  rm -rf "$out/templates/tests"
done
cp "$src"/values/*.yaml "$dst/values/"
chmod -R a+rX "$dst"
( cd "$src" && git log -1 --format='upstream helm/ at %H (%cs)' -- . 2>/dev/null || echo 'upstream helm/ (not a git checkout)' ) > "$dst/SOURCE"
if [ -n "$check" ]; then
  # SOURCE only records the commit: compare the content.
  if ! diff -r -q -x SOURCE "$assets" "$dst"; then
    echo "embedded charts differ from $src: run 'make charts' and release the operator" >&2
    exit 1
  fi
  echo "embedded charts match $src ($(cat "$dst/SOURCE"))"
  exit 0
fi
echo "synced ${#charts[@]} charts into $dst"
