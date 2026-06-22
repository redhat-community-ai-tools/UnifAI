# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Local Development Quickstart

All service lifecycle management goes through the `unifai-dev` CLI (Typer-based, lives in `local-development/`):

```bash
# Install the CLI once
pipx install -e local-development/

# First-time setup: creates venvs, installs deps, starts infra containers
unifai-dev init

# Start all services
unifai-dev start all

# Start a single service in the foreground (for log visibility / debugging)
unifai-dev start <service> --fg
# Valid service names: backend, rag, multi-agent, ui
# Valid group names: all, services, workers, agents, rag-stack, backend-only
#   rag-stack  = rag + celery worker
#   agents     = multi-agent + temporal-worker
```

For the UI without `unifai-dev`:

```bash
cd ui && pnpm install && pnpm dev
```

Node.js ≥22 and pnpm are required for the UI. Python 3.11–3.13 is required for all backend services (3.14+ is not supported).

### Service Ports

| Service        | Port  | UI Proxy Path |
|----------------|-------|---------------|
| Backend        | 8005  | `/api4`       |
| RAG            | 13457 | `/api1`       |
| Multi-Agent    | 8002  | `/api2`       |
| Identity       | 13456 | `/api3`       |
| UI (Vite)      | 5000  | —             |

### Venv and `global_utils`

Each Python service uses its own venv. The `global_utils` shared package **must** be installed as editable into every service's venv:

```bash
# unifai-dev handles this automatically, but manually:
unifai-dev venv setup          # sets up all venvs
# or per-service:
source <service>/venv/bin/activate
pip install -e shared-resources/global_utils/
pip install -e <service>/
```

### Local Auth

For development, set `local_auth: true` in `local-development/services.yaml` — this bypasses SSO and removes the need for IdP credentials.

---

## Running Tests

Tests use **pytest** with custom markers. Run inside the target service venv or via `unifai-dev exec`:

```bash
# Via unifai-dev (runs inside the service's venv)
unifai-dev exec <service> python -m pytest tests/

# Run a single test file
unifai-dev exec <service> python -m pytest tests/unit/test_something.py

# Run by marker
unifai-dev exec <service> python -m pytest tests/ -m unit
unifai-dev exec <service> python -m pytest tests/ -m integration
unifai-dev exec <service> python -m pytest tests/ -m e2e
```

Available pytest markers: `unit`, `integration`, `e2e`, `agent_system`, `stress`, `performance`.

Test files live under `tests/` in each service directory, named `test_*.py`. Fixtures go in `conftest.py`.

---

## System Architecture

### Five Services

```
ui/                     React 18 + TypeScript + Vite (port 5000)
backend/                Platform service — admin config (port 8005)
rag/                    RAG pipeline + document ingestion (port 13457)
multi-agent/            Agentic workflow engine (port 8002)
shared-resources/
  identity/             Auth + user management (port 13456)
  global_utils/         Shared Python utilities (installed editable everywhere)
```

### Hexagonal Architecture (RAG and MAS services)

Both `rag/` and `multi-agent/` enforce strict **Ports & Adapters** layering. The dependency direction is **one-way and non-negotiable**:

```
Adapters  →  Application  →  Domain
```

- **Domain layer**: Pure business logic, zero external imports (no Flask, no MongoDB, no HTTP clients).
- **Application layer**: Orchestrates domain using injected port interfaces (abstract base classes).
- **Adapters layer**: Implements ports — Flask endpoints, MongoDB repositories, HTTP clients, LangGraph/Temporal runners.

Violating this direction (e.g., a domain class importing from an adapter) is a **CRITICAL** architecture violation and must be rejected.

#### Severity Classification for Reviews

| Severity | Examples |
|----------|----------|
| CRITICAL | Domain importing infrastructure; Adapter bypassing Application layer |
| MAJOR    | Cyclic imports between layers; concrete deps instead of ports |
| MINOR    | Naming inconsistencies; missing type hints |
| ALIGNMENT | Inconsistent with established project patterns |

### Dependency Injection Pattern

Every service has a **singleton `AppContainer`** (composition root) wired at startup in `bootstrap/` or `core/app_container.py`. It creates and owns all shared resources (DB clients, repositories, services) and wires them together. Endpoints access it via `current_app.container`. **Never instantiate infrastructure objects outside the container.**

### Blueprint DSL (Multi-Agent)

Multi-agent workflows are defined as **Blueprints** — YAML files describing a graph of nodes with conditions and plan DAGs. These are loaded and executed by either:
- **LangGraph** — local, in-process execution
- **Temporal** — distributed, durable execution

The execution engine is selectable at runtime. Blueprints are not Python code; they describe *what* to run, not *how*.

### Element Catalog (Multi-Agent)

Nodes, tools, LLMs, and retrievers are **auto-discovered pluggable components**. Adding a new component means dropping a file in the right directory — the catalog picks it up without manual registration. Do not hardcode component lists.

### RAG Pipeline Architecture

Document ingestion runs as a **Celery + RabbitMQ** async pipeline. Heavy compute steps (docling parsing, embedding generation) can be offloaded to **remote services** controlled by feature flags:

```
USE_REMOTE_DOCLING=true   # delegate PDF parsing to a remote docling service
USE_REMOTE_EMBEDDING=true # delegate embedding to a remote model service
```

When these flags are `false`, the libraries are loaded locally. **Lazy imports** are used — `import docling` and `import torch` only happen when the local adapters are actually invoked.

### Admin Config System (Backend)

The config UI is driven by a **static template** (`backend/admin_config/template.py`) that defines a `Template → Category → Section → Field` hierarchy. MongoDB stores only the *overridden values*; at read time, stored values are merged with the template. The UI renders dynamically from this merged response and never hardcodes field definitions.

When a config section is saved, `ActionDispatcher` POSTs to the target service's `on_update_endpoint` to propagate the change (e.g., updating Slack channel restrictions notifies the RAG service).

### UI HTTP Clients

The UI maintains **three separate Axios instances** — one per backend service:

| Axios Instance | Target        | Base Path |
|----------------|---------------|-----------|
| `api1`         | RAG           | `/api1`   |
| `api2`         | Multi-Agent   | `/api2`   |
| `api3`         | Identity      | `/api3`   |

Streaming responses use **Oboe.js**. Graph visualization uses **JointJS**. UI components are built with **shadcn/ui** (Radix UI + Tailwind CSS).

---

## Code Quality Rules (from Cursor rules)

### Architecture Reviews

When reviewing or writing code for `rag/` or `multi-agent/`, validate:
1. **Dependency flow** — Adapters → Application → Domain only. No reverse imports.
2. **Layer separation** — Domain has zero external library imports. Application speaks only in ports (interfaces).
3. **No parallel implementations** — Do not add a new adapter alongside an existing one; replace it.
4. **No dead code** — No commented-out implementations, no TODO stubs, no unused imports.

Required verdict format for architecture reviews: `APPROVE` / `APPROVE WITH CHANGES` / `REJECT`.

### Refactoring Rules

- **Replace, don't layer** — when refactoring, remove the old implementation. Never leave both old and new running in parallel.
- No placeholder implementations (no `pass`, no `raise NotImplementedError` left in production paths).
- Clean up all dead code and commented leftovers as part of the change.

### Code Health Reviews

When reviewing any code, flag:
- **Duplicated logic** across modules that should be extracted
- **Dead/unused code** — unreachable branches, unused variables, imports never called
- **Over-engineering** — abstractions with a single implementation and no extension plan

Code Health Score is 0–10. Verdict: `CLEAN` / `NEEDS REFACTORING` / `MAJOR CLEANUP REQUIRED`.

---

## Deployment (Reference)

CI uses **Jenkins + Podman** with two pipelines:
- `ci/pipeline-build.groovy` — builds and pushes container images (parallel per service)
- `ci/pipeline-deploy.groovy` — Helmfile-based OpenShift deployment

Image names: `backend`, `multiagentbackend`, `ui`, `identity`. Registry: `images.paas.redhat.com/unifai/`. Tags are date-based (`YYYY.MM.DD`).

Kubernetes/OpenShift deployment uses **Helm + Helmfile** in three tiers:
1. **Tier 1** — Shared infra (MongoDB, RabbitMQ, Qdrant)
2. **Tier 2** — App services (RAG, MAS, Identity)
3. **Tier 3** — Frontend (UI + Nginx)

Deploy strategies: `FRESH_INSTALL` (~30–45 min, deletes everything) or `APPLICATION_UPGRADE` (~5–10 min rolling update).
