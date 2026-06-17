# UnifAI Developer Guide

An interactive, visual map of the UnifAI system architecture. Serves two audiences:

- **Humans** — open `index.html` to browse services, features, and class architectures in an interactive SVG map.
- **AI agents** — read `docs/services/*.md` for per-service knowledge (architecture, endpoints, class hierarchies, blast radius). The Cursor skill tree routes agents here via `source-map.yaml` path globs.

## Quick Start

```bash
# Option 1: open directly
xdg-open index.html        # Linux
open index.html             # macOS

# Option 2: serve locally (avoids file:// CORS issues)
python3 -m http.server 8080
# then visit http://localhost:8080
```

Or build the single-file artifact:

```bash
bash build.sh
# produces unifai-dev-guide.html (~400 KB, self-contained except Google Fonts)
```

## How to Use the Interactive Guide

- **Pan** — click and drag the background
- **Zoom** — scroll wheel, or `+`/`-` buttons in the bottom-right corner
- **Explore a service** — click any node to open its detail panel
- **Detail panel tabs** — Job Description, Interfaces, Architecture, Interactions
- **Views** — switch between Map, Services, and Features via the header tabs
- **Keyboard** — `+`/`-` to zoom, `0` to fit, `Esc` to close panel

## Repository Structure

```text
unifai-dev-guide/
│
├── index.html                         # Dev entry point — loads split scripts in dependency order
├── build.sh                           # Produces single-file unifai-dev-guide.html artifact
├── validate.js                        # Schema + referential integrity validation for all data files
├── gen-docs.js                        # Generates docs/services/*.md + blast-radius.md from JS data
│
├── css/
│   └── styles.css                     # Full dark theme (~1200 lines): map nodes, panels, flow timelines
│
├── js/
│   ├── data/
│   │   ├── _registry.js               # Defines NODE_TYPES + empty SERVICES/FEATURES/EDGES containers
│   │   ├── _edges.js                  # 24 service-to-service runtime connections (from/to/label/protocol)
│   │   ├── services/                  # One JS file per service (16 files), populates SERVICES global
│   │   │   ├── browser.js             #   External entry point
│   │   │   ├── ui.js                  #   React SPA + Nginx reverse proxy (~33 KB)
│   │   │   ├── rag.js                 #   Document & vector search service (~27 KB)
│   │   │   ├── mas.js                 #   Multi-agent orchestration engine (~53 KB)
│   │   │   ├── identity.js            #   Auth & session service
│   │   │   ├── platform.js            #   Admin configuration service
│   │   │   ├── celery.js              #   RAG async ingestion workers
│   │   │   ├── temporal_worker.js     #   MAS distributed graph execution worker
│   │   │   ├── mongodb.js             #   Document database
│   │   │   ├── qdrant.js              #   Vector database
│   │   │   ├── rabbitmq.js            #   Celery message broker
│   │   │   ├── redis.js               #   Streaming, sessions & collaboration
│   │   │   ├── temporal.js            #   Workflow orchestration server
│   │   │   ├── keycloak.js            #   Identity provider (OIDC)
│   │   │   ├── slack.js               #   Slack API (disabled)
│   │   │   └── global_utils.js        #   Shared Python library (all backends)
│   │   └── features/                  # One JS file per end-to-end feature flow (6 files)
│   │       ├── feat_inventory.js      #   Agentic AI Inventory
│   │       ├── feat_workflows.js      #   Agentic AI Workflows
│   │       ├── feat_chats.js          #   Chats (Sessions) — largest flow
│   │       ├── feat_rag.js            #   RAG Data Pipeline
│   │       ├── feat_overview.js       #   Overview Dashboards
│   │       └── feat_team_workspace.js #   Team Workspace
│   │
│   ├── data-classes/                  # Class-level architecture per service (8 files)
│   │   ├── _registry.js               #   Empty SERVICE_CLASSES container
│   │   ├── mas.js                     #   MAS: 13 layers, 77 classes, calls/calledBy graphs
│   │   ├── rag.js                     #   RAG: 12 layers, 58 classes
│   │   ├── ui.js                      #   UI: 8 layers, 35 components/hooks/contexts
│   │   ├── identity.js                #   Identity: 5 layers, 15 classes
│   │   ├── platform.js                #   Platform: 4 layers, 11 classes
│   │   ├── global_utils.js            #   global_utils: 5 layers, 22 classes
│   │   ├── celery.js                  #   Celery: 3 layers, 9 classes (shared RAG codebase)
│   │   └── temporal_worker.js         #   Temporal Worker: 4 layers, 8 classes (shared MAS codebase)
│   │
│   ├── lib/
│   │   └── marked.min.js             # Markdown → HTML renderer (marked v12)
│   │
│   ├── map.js                         # MapRenderer: SVG service graph, curved edges, feature dividers
│   ├── views.js                       # ViewManager: Services/Features tab grids, section nav, tables
│   └── interactions.js                # Interactions: pan, zoom, tooltips, detail panel with tabs
│
├── docs/
│   └── services/                      # Auto-generated markdown docs (via gen-docs.js)
│       ├── README.md                  #   Index of all generated docs
│       ├── blast-radius.md            #   Cross-service dependency impact analysis
│       ├── mas.md                     #   MAS reference (614 lines) — largest doc
│       ├── rag.md                     #   RAG reference (469 lines)
│       ├── ui.md                      #   UI reference (413 lines)
│       └── ... (16 service docs)      #   One per service
│
├── topology.yaml                      # Service graph source of truth — 16 services, 24 edges, 6 features
│                                      #   with types, positions, tech stacks, code roots, protocols
│
├── source-map.yaml                    # Maps UnifAI monorepo code paths to dev-guide services
│                                      #   Endpoint globs, port ABCs, Mongo collections, UI API modules
│                                      #   Includes elementCategories for MAS sub-domain skill routing
│
├── guide-sync.json                    # Sync metadata: last commit SHA, per-service structured data counts
│
├── .cursor/rules/
│   └── dev-guide.md                   # Agent instructions: schemas, update contract, reference formats
│
├── .github/workflows/
│   ├── validate.yml                   # CI: runs validate.js + build.sh on PR/push to main
│   └── sync-guide.yml                 # Sync: triggered by UnifAI repo dispatch, creates PR with updates
│
└── .gitignore                         # Ignores build artifact + legacy monolithic data files
```

## Data Architecture

All data lives in global JavaScript variables (no ES modules, no bundler):

| Global | Populated by | Contains |
|--------|-------------|----------|
| `NODE_TYPES` | `_registry.js` | Color/style config for service types (APP, WORKER, INFRA, etc.) |
| `SERVICES` | `services/*.js` | 16 service definitions with metadata, prose, endpoints, ports, diagrams |
| `FEATURES` | `features/*.js` | 6 end-to-end user journey definitions with flows and code walkthroughs |
| `EDGES` | `_edges.js` | 24 runtime connections between services (protocol, label, detail) |
| `SERVICE_CLASSES` | `data-classes/*.js` | Class-level architecture: layers, classes, `calls`/`calledBy` dependency graphs |

### calls/calledBy Convention

Class architecture files use a normalized reference format in `calls` and `calledBy` arrays:

| Format | Meaning | Example |
|--------|---------|---------|
| `ClassName` | Class in the same service | `'BlueprintService'` |
| `service:ClassName` | Class in another service | `'global_utils:SharedConfig'` |
| `HTTP: /path/` | HTTP endpoint consumer | `'HTTP: /sessions/'` |
| `Celery: task` | Celery task trigger | `'Celery: execute_pipeline_task'` |
| `Temporal: dispatch` | Temporal workflow trigger | `'Temporal: dispatch'` |
| `Flask: router` | Flask framework routing | `'Flask: router'` |
| `entrypoint` | Process entry point | `'entrypoint'` |
| `* description` | Aggregate high-fanout marker | `'* element specs (...)'` |
| lowercase | External library | `'pymongo'`, `'redis'`, `'axios'` |

## Tooling

### `validate.js`

```bash
node validate.js
```

Checks all data files for:
- Syntax errors (loads every JS file in a VM sandbox)
- Required fields on every service and feature
- EDGES and FEATURES reference valid service IDs
- `_endpoints` entries have `method` and `path`
- `_ports` entries have `name`
- Cross-service class references (`service:Class`) target valid service IDs

### `gen-docs.js`

```bash
node gen-docs.js                     # generate all service docs + blast-radius
node gen-docs.js --blast-radius-only  # generate blast-radius.md only
node gen-docs.js --skip-blast-radius  # generate service docs only
```

Generates `docs/services/*.md` from live JS data. Each service doc consolidates metadata, connections, features, job description, endpoints, ports, architecture prose, key extension points, and full class architecture. Also generates `docs/services/blast-radius.md` with cross-service dependency analysis and impact rankings.

### `build.sh`

```bash
bash build.sh
```

Concatenates all JS data files in dependency order, inlines CSS + marked + rendering code into a single `unifai-dev-guide.html` (~400 KB). Only external dependency: Google Fonts (Poppins, Inter, Fira Code).

## Editing Content

Each service has its own file in `js/data/services/`. To update a service:

1. Read `docs/services/<id>.md` to understand the current state
2. Edit `js/data/services/<id>.js` (prose in Markdown, structured arrays auto-extracted)
3. Optionally edit `js/data-classes/<id>.js` for class architecture
4. Run `node validate.js` to check for errors
5. Run `node gen-docs.js` to regenerate reference docs
6. Refresh browser or run `bash build.sh` for the portable artifact

### Update Contract

| Field | Who updates | Rules |
|-------|-------------|-------|
| `_endpoints`, `_ports`, `_config`, `_collections` | Extraction script | Fully automated from source code |
| `job`, `interfaces`, `architecture` | AI agent | Use judgment; Markdown or HTML |
| `modal.*` | AI agent | Keep concise (2-3 paragraphs max) |
| `x`, `y`, `w`, `h` | Human only | Visual layout positions — never touch |
| `scheme` | Human only | Diagram coordinates — never touch |
| `flow`, `codeFlow` | AI agent | Step-by-step arrays |
| EDGES (in `_edges.js`) | Semi-automated | Derived from `topology.yaml` |
| `calls`, `calledBy` | AI agent | Follow reference format convention above |

## Automated Sync

The guide stays in sync with the UnifAI monorepo through two GitHub Actions:

- **`validate.yml`** — runs on every PR/push to main: `node validate.js` + `bash build.sh`
- **`sync-guide.yml`** — triggered by `repository_dispatch` from UnifAI on merge to main: checks out both repos, runs validation and build, creates a PR if changes detected

Key files for sync:
- `source-map.yaml` — defines which UnifAI code paths map to which service data (endpoint globs, port ABCs, Mongo collections, UI API modules, element categories)
- `guide-sync.json` — tracks the last sync commit SHA and per-service structured data counts
- `.cursor/rules/dev-guide.md` — agent instructions for what fields to update and how

## Adding a New Service

1. Create `js/data/services/<service_id>.js` with the service schema
2. Add edges in `js/data/_edges.js`
3. Optionally add class data in `js/data-classes/<service_id>.js`
4. Add `<script>` tags in `index.html` and file entries in `build.sh` arrays
5. Run `node validate.js` and `bash build.sh`
6. Run `node gen-docs.js` to regenerate all reference docs
