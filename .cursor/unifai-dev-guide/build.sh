#!/usr/bin/env bash
# Builds a single self-contained HTML file from the dev guide sources.
# Usage: bash build.sh  →  produces unifai-dev-guide.html
set -euo pipefail
cd "$(dirname "$0")"

OUT="unifai-dev-guide.html"

# --- Concatenate split data files in dependency order ---
DATA_SERVICE_FILES=(
  js/data/services/browser.js
  js/data/services/ui.js
  js/data/services/rag.js
  js/data/services/mas.js
  js/data/services/identity.js
  js/data/services/platform.js
  js/data/services/celery.js
  js/data/services/temporal_worker.js
  js/data/services/mongodb.js
  js/data/services/qdrant.js
  js/data/services/rabbitmq.js
  js/data/services/redis.js
  js/data/services/temporal.js
  js/data/services/keycloak.js
  js/data/services/slack.js
  js/data/services/global_utils.js
)

DATA_FEATURE_FILES=(
  js/data/features/feat_inventory.js
  js/data/features/feat_workflows.js
  js/data/features/feat_chats.js
  js/data/features/feat_rag.js
  js/data/features/feat_overview.js
  js/data/features/feat_team_workspace.js
)

DATA_CLASSES_FILES=(
  js/data-classes/rag.js
  js/data-classes/mas.js
  js/data-classes/identity.js
  js/data-classes/platform.js
  js/data-classes/global_utils.js
  js/data-classes/celery.js
  js/data-classes/temporal_worker.js
  js/data-classes/ui.js
)

# Assemble JS_DATA: registry + services + edges + features
JS_DATA=$(cat js/data/_registry.js)
for f in "${DATA_SERVICE_FILES[@]}"; do
  JS_DATA+=$'\n'"$(cat "$f")"
done
JS_DATA+=$'\n'"$(cat js/data/_edges.js)"
for f in "${DATA_FEATURE_FILES[@]}"; do
  JS_DATA+=$'\n'"$(cat "$f")"
done

# Assemble JS_DATA_CLASSES: registry + per-service
JS_DATA_CLASSES=$(cat js/data-classes/_registry.js)
for f in "${DATA_CLASSES_FILES[@]}"; do
  JS_DATA_CLASSES+=$'\n'"$(cat "$f")"
done

CSS=$(cat css/styles.css)
JS_MARKED=$(cat js/lib/marked.min.js 2>/dev/null || echo "")
JS_MAP=$(cat js/map.js)
JS_VIEWS=$(cat js/views.js)
JS_INTER=$(cat js/interactions.js)

cat > "$OUT" <<'HEADER'
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>UnifAI — Developer Guide</title>
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23a855f7' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'><polygon points='12 2 2 7 12 12 22 7 12 2'/><polyline points='2 17 12 22 22 17'/><polyline points='2 12 12 17 22 12'/></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&family=Inter:wght@300;400;500&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
HEADER

echo "$CSS" >> "$OUT"

cat >> "$OUT" <<'MID1'
  </style>
</head>
<body>
  <header id="top-bar">
    <div class="logo">
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="#BB86FC" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <polygon points="12 2 2 7 12 12 22 7 12 2"/>
        <polyline points="2 17 12 22 22 17"/>
        <polyline points="2 12 12 17 22 12"/>
      </svg>
      <span>UnifAI</span>
      <span class="subtitle">Developer Guide</span>
      <span class="separator">|</span>
      <span class="subtitle">powered by Applied AI Enablement Team (part of UIE)</span>
    </div>
    <nav id="view-tabs">
      <button class="view-tab active" data-view="map">Map</button>
      <button class="view-tab" data-view="services">Services</button>
      <button class="view-tab" data-view="features">Features</button>
    </nav>
  </header>

  <div id="legend-bar">
    <span class="legend-item"><span class="legend-dot app"></span>Application Service</span>
    <span class="legend-item"><span class="legend-dot worker"></span>Worker / Process</span>
    <span class="legend-item"><span class="legend-dot infra"></span>Infrastructure</span>
    <span class="legend-item"><span class="legend-dot external"></span>External / Optional</span>
    <span class="legend-item"><span class="legend-dot feature"></span>Feature Flow</span>
    <span class="legend-item"><span class="legend-dot shared"></span>Shared Library</span>
    <span class="legend-item"><span class="legend-dot disabled"></span>Disabled</span>
  </div>

  <main id="map-container" class="view-content active">
    <div id="map-viewport">
      <svg id="map-svg"></svg>
    </div>
  </main>

  <section id="services-view" class="view-content">
    <div id="services-grid" class="item-grid"></div>
    <nav id="services-section-nav" class="section-nav hidden"></nav>
    <div id="services-content" class="content-area"></div>
  </section>

  <section id="features-view" class="view-content">
    <div id="features-grid" class="item-grid"></div>
    <nav id="features-section-nav" class="section-nav hidden"></nav>
    <div id="features-content" class="content-area"></div>
  </section>

  <div id="zoom-controls">
    <button id="zoom-in" title="Zoom in">+</button>
    <button id="zoom-fit" title="Fit all">⊡</button>
    <button id="zoom-out" title="Zoom out">−</button>
  </div>

  <div id="detail-panel" class="hidden">
    <button id="panel-close" title="Close">&times;</button>
    <div id="panel-header">
      <div id="panel-icon"></div>
      <div>
        <h2 id="panel-title"></h2>
        <p id="panel-subtitle"></p>
      </div>
    </div>
    <nav id="panel-tabs">
      <button class="tab active" data-tab="job">Job Description</button>
      <button class="tab" data-tab="interfaces">Interfaces</button>
      <button class="tab" data-tab="architecture">Architecture</button>
      <button class="tab" data-tab="scheme">Interactions</button>
    </nav>
    <div id="panel-body">
      <div id="tab-job" class="tab-content active"></div>
      <div id="tab-interfaces" class="tab-content"></div>
      <div id="tab-architecture" class="tab-content"></div>
      <div id="tab-scheme" class="tab-content"></div>
    </div>
  </div>

  <div id="tooltip" class="hidden"></div>

  <script>
MID1

[ -n "$JS_MARKED" ] && { echo "$JS_MARKED" >> "$OUT"; echo "" >> "$OUT"; }
echo "$JS_DATA" >> "$OUT"
echo "" >> "$OUT"
echo "$JS_DATA_CLASSES" >> "$OUT"
echo "" >> "$OUT"
echo "$JS_MAP" >> "$OUT"
echo "" >> "$OUT"
echo "$JS_VIEWS" >> "$OUT"
echo "" >> "$OUT"
echo "$JS_INTER" >> "$OUT"

cat >> "$OUT" <<'FOOTER'
  </script>
</body>
</html>
FOOTER

SIZE=$(wc -c < "$OUT")
echo "✓ Built $OUT ($(( SIZE / 1024 )) KB)"
