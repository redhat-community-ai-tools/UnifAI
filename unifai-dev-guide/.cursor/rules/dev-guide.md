---
description: Agent instructions for updating the UnifAI Developer Guide
globs: ["js/data/**/*.js", "js/data-classes/**/*.js"]
---

# UnifAI Developer Guide — Agent Update Instructions

## Repository Purpose

This repo is an interactive visual guide to the UnifAI system architecture. It renders as a static HTML app (no bundler) showing a service map, detail panels, and tabbed views for services and features.

## File Structure

```
js/
  data/
    _registry.js          # NODE_TYPES + empty SERVICES/FEATURES/EDGES containers (load first)
    _edges.js             # Service-to-service connections (load last in data layer)
    services/
      <service_id>.js     # One file per service (e.g., rag.js, mas.js)
    features/
      <feature_id>.js     # One file per feature (e.g., feat_inventory.js)
  data-classes/
    _registry.js          # Empty SERVICE_CLASSES container
    <service_id>.js       # Class-level architecture per service
  lib/
    marked.min.js         # Markdown renderer (v12)
  map.js                  # SVG map rendering
  views.js                # Services/Features tab rendering
  interactions.js         # Pan, zoom, detail panel
```

## Data Schema: Service File

```javascript
SERVICES.<service_id> = {
  id: '<service_id>',           // Must match filename and object key
  name: 'Display Name',         // Human-readable, e.g. "Multi Agent System (MAS)"
  icon: '🤖',                   // Single emoji
  role: 'Short tagline',        // 3-8 words
  type: 'APP',                  // One of: APP, WORKER, INFRA, EXTERNAL, SHARED, DISABLED
  x: 600, y: 380,              // DO NOT MODIFY — visual layout positions
  w: 190, h: 60,               // DO NOT MODIFY — visual layout sizes

  detail: {
    subtitle: 'Tech stack summary • Port NNNN',

    // --- Prose content (agent-updatable) ---
    job: `...`,                  // Job description — what this service does
    interfaces: `...`,           // API surface description
    architecture: `...`,         // Internal architecture description
    architectureNotes: `...`,    // Optional supplementary notes

    // --- Modal (shorter versions for map side panel) ---
    modal: {                     // Optional — if omitted, full content is used
      job: `...`,
      interfaces: `...`,
      architecture: `...`,
    },

    // --- Structured data (auto-extracted, prefixed with _) ---
    _endpoints: [
      { method: 'POST', path: '/docs/upload', summary: 'multipart file upload', group: 'Documents' },
    ],
    _ports: [
      { name: 'VectorRepository', role: 'store/search/delete embeddings', adapter: 'Qdrant' },
    ],
    _collections: [
      { db: 'rag_db', collection: 'pipelines' },
    ],
    _config: [
      { key: 'port', default: '13456', purpose: 'Flask server port' },
    ],

    // --- Diagram (DO NOT MODIFY without explicit request) ---
    scheme: { nodes: [...], edges: [...] },
  },
};
```

## Data Schema: Feature File

Features extend the service schema with additional fields:

```javascript
FEATURES.<feature_id> = {
  // ... same base fields as services ...
  services: ['ui', 'mas', 'mongodb'],  // Which services participate

  detail: {
    // ... same prose + structured fields ...

    flow: [
      { step: 1, label: 'User action', actor: 'UI', detail: 'description' },
    ],
    codeFlow: [
      { step: 1, label: 'Route loads', actor: 'UI', detail: '<code>Component.tsx</code>' },
    ],
    dataModel: `...`,
    devScenarios: `...`,
    dependencies: {
      requires: [{ featureId: 'feat_x', reason: '...' }],
      requiredBy: [{ featureId: 'feat_y', reason: '...' }],
    },
  },
};
```

## Content Format Rules

1. **New prose content**: Write in **Markdown**. The renderer auto-detects: if content starts with `<`, it's treated as HTML; otherwise it's parsed with `marked.parse()`.

2. **Existing HTML content**: Do NOT convert existing HTML to Markdown unless explicitly asked. It uses custom CSS classes that Markdown can't replicate.

3. **Structured arrays** (`_endpoints`, `_ports`, `_collections`, `_config`): These are auto-rendered by `views.js` into HTML tables/lists. They complement (not replace) the prose HTML.

## Update Contract

| Field | Who updates | Rules |
|-------|-------------|-------|
| `_endpoints`, `_ports`, `_config`, `_collections` | Extraction script | Fully automated from source code |
| `job`, `interfaces`, `architecture` | AI agent | Use judgment; can be markdown or HTML |
| `modal.*` | AI agent | Keep concise (2-3 paragraphs max) |
| `x`, `y`, `w`, `h` | Human only | Visual layout — never touch |
| `scheme` | Human only | Diagram coordinates — never touch |
| `flow`, `codeFlow` | AI agent | Step-by-step arrays |
| EDGES (in `_edges.js`) | Semi-automated | Derived from `topology.yaml` |

## Naming Conventions

- Service IDs: `snake_case` (e.g., `temporal_worker`, `global_utils`)
- Feature IDs: `feat_` prefix + `snake_case` (e.g., `feat_inventory`)
- Display names: Full proper names (e.g., "Multi Agent System (MAS)" not "MAS API")
- File names: Match the service/feature ID exactly (e.g., `temporal_worker.js`)

## Data Schema: Class Architecture File

```javascript
SERVICE_CLASSES.<service_id> = {
  description: `<p>...</p>`,
  layers: [
    {
      name: 'Layer Name',
      classes: [
        {
          name: 'ClassName',          // Or 'ClassName (ABC)' for abstract classes
          file: 'relative/path.py',   // Relative to service code root
          role: 'What this class does',
          calls: ['OtherClass', ...], // What this class depends on
          calledBy: ['Consumer', ...] // What depends on this class
        },
      ]
    },
  ],
  scheme: { nodes: [...], edges: [...] },  // DO NOT MODIFY — diagram coordinates
};
```

### calls/calledBy Reference Format

References in `calls` and `calledBy` arrays follow a strict naming convention for machine-resolvability:

| Format | Meaning | Example |
|--------|---------|---------|
| `ClassName` | Class in the same service | `'BlueprintService'` |
| `service:ClassName` | Class in another service | `'global_utils:SharedConfig'` |
| `HTTP: /path/` | HTTP endpoint consumer | `'HTTP: /sessions/'` |
| `Celery: task_name` | Celery task trigger | `'Celery: execute_pipeline_task'` |
| `Temporal: dispatch` | Temporal workflow trigger | `'Temporal: dispatch'` |
| `Flask: router` | Flask framework routing | `'Flask: router'` |
| `entrypoint` | Process entry point (CLI/WSGI) | `'entrypoint'` |
| `* description` | Aggregate high-fanout (many subclasses) | `'* element specs (nodes, llms, ...)'` |
| lowercase name | External library (not in our code) | `'pymongo'`, `'redis'`, `'axios'` |

Cross-service references (`service:Class`) are validated by `validate.js` — the service prefix must match a known service ID in `SERVICE_CLASSES`.

## Validation

After any edit, run: `node validate.js`

This checks:
- All files parse without syntax errors
- Required fields exist on every service/feature
- EDGES reference valid service IDs
- FEATURES reference valid service IDs in their `services` array
- `_endpoints` entries have `method` and `path`
- `_ports` entries have `name`
- Cross-service references in `calls`/`calledBy` target valid service IDs

## Build

Run `bash build.sh` to produce the single-file `unifai-dev-guide.html` artifact.

## Per-Service Reference Docs

Each service has a comprehensive markdown reference at `docs/services/<service_id>.md`.
These files consolidate all data (metadata, connections, job description, endpoints, ports, architecture, class diagrams) into a single readable document per service.

**Usage by agents:** Before updating a service, read its `docs/services/<id>.md` to understand the current state. After updating `js/data/services/<id>.js`, regenerate docs:

```bash
node gen-docs.js
```

These docs are the primary reference for the Cursor agent skill when performing updates.

## Blast Radius Doc

`docs/services/blast-radius.md` is auto-generated by `gen-docs.js` from `js/data/_edges.js` (service-level connections) and `js/data-classes/*.js` (class-level `calls`/`calledBy` graphs). It provides:

- Service-level dependency matrix
- Cross-service class dependencies (derived from `service:Class` notation)
- Base class impact analysis (ABCs and base classes ranked by downstream reach)
- High-coupling hotspots (classes with highest in-degree)
- Per-service risk summary

**Do NOT edit `blast-radius.md` manually** — regenerate it:

```bash
node gen-docs.js                    # regenerate all docs + blast-radius
node gen-docs.js --blast-radius-only # regenerate blast-radius only
node gen-docs.js --skip-blast-radius # regenerate service docs only
```

## Source Map for Domain Skills

`source-map.yaml` maps UnifAI monorepo code paths to dev-guide services. It includes an `elementCategories` section under `mas:` that provides per-element-category globs for deriving Cursor domain skill `paths:` directives:

```yaml
mas:
  elementCategories:
    nodes:
      glob: "multi-agent/lib/mas/elements/nodes/**"
      baseClass: BaseNode
      docSection: "mas.md → Elements Plugin Layer"
```

Domain skills should derive their `paths:` globs from this section rather than hardcoding paths.

## Adding a New Service

1. Create `js/data/services/<service_id>.js` with the schema above
2. Add edges in `js/data/_edges.js`
3. Optionally add class data in `js/data-classes/<service_id>.js`
4. Update `index.html` script tags and `build.sh` DATA_SERVICE_FILES array
5. Run `node validate.js` and `bash build.sh`
6. Run `node gen-docs.js` to regenerate reference docs
