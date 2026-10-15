#!/usr/bin/env bash
# Copies the upstream charts and values deployed by UnifaiStack into internal/stack/assets (embedded in the binary).
# Upstream files are copied verbatim: every fork-specific setting (images, storage classes, URLs, resources) is applied
# by the operator at render time (internal/stack), never by editing charts. Run from fork/unifai-operator: `make charts`.
set -euo pipefail
src=${1:-../../helm}
dst=internal/stack/assets
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
( cd "$src" && git log -1 --format='upstream helm/ at %H (%cs)' -- . ) > "$dst/SOURCE"
echo "synced ${#charts[@]} charts into $dst"
