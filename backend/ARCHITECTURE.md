# Backend (Platform Service)

## Overview

Lightweight Flask service (port 8005, proxied via `/api4` from the UI) for cross-cutting platform concerns. Currently handles **admin configuration**; designed to grow with new domains.

This is a separate service from:
- **RAG / Data Pipeline Hub** (port 13457, `/api1`) — document ingestion, Slack pipelines, embeddings
- **Multi-Agent System** (port 8002, `/api2`) — agentic workflows, sessions, blueprints
- **Identity Service** (port 13456, `/api3`) — authentication, user management

---

## Project Structure

```
backend/
├── api/
│   └── flask/
│       ├── flask_app.py            # Application factory (create_app)
│       └── endpoints/
│           ├── __init__.py         # Blueprint registration
│           ├── health.py           # Health check endpoint
│           └── admin_config.py     # Admin config REST endpoints
├── admin_config/
│   ├── models.py                   # Pydantic models (template + stored + merged)
│   ├── template.py                 # Static config template definition
│   ├── service.py                  # Business logic (get, update, access check)
│   ├── action_dispatcher.py        # Side-effect HTTP calls to other services
│   └── repository/
│       ├── repository.py           # Abstract repository interface
│       └── mongo_repository.py     # MongoDB implementation
├── config/
│   └── app_config.py               # Environment configuration
├── core/
│   └── app_container.py            # Composition root / dependency injection
├── shared/
│   └── logger.py                   # Logging setup
├── run/
│   ├── dev.py                      # Development server entry point
│   └── wsgi.py                     # Production WSGI entry point
├── Dockerfile
├── entrypoint.sh
└── requirements.txt
```

---

## Architecture

### Layers

| Layer | Location | Responsibility |
|-------|----------|----------------|
| **HTTP** | `api/flask/endpoints/` | Parse requests, call service, return JSON |
| **Service** | `admin_config/service.py` | Business logic, validation, orchestration |
| **Repository** | `admin_config/repository/` | MongoDB persistence |
| **Side-effects** | `admin_config/action_dispatcher.py` | HTTP POST to other internal services |
| **Composition** | `core/app_container.py` | Wires all dependencies (singleton) |
| **Config** | `config/app_config.py` | Environment-driven settings |

### Request Flow

```
HTTP Request
  → Flask Blueprint (endpoint layer — parse args, delegate)
    → AdminConfigService (business logic)
      → AdminConfigRepository (read/write MongoDB)
      → ActionDispatcher (POST to downstream services on update)
  ← JSON Response
```

### Dependency Injection

`AppContainer` is a singleton created at app startup in `create_app()`. It owns:
- The shared `MongoClient` (single connection pool)
- `AdminConfigRepository` (bound to the `admin_config` collection)
- `ActionDispatcher` (configured with internal service URLs)
- `AdminConfigService` (wired with repo, template, and dispatcher)

The container is attached to `app.container` and accessed in endpoints via `current_app.container`.

---

## Admin Config System

### Template-Driven Design

The config page is entirely driven by a **static template** (`template.py`) that defines:

```
Template → Category → Section → Field
```

- **Category**: top-level tab in the UI (e.g., "Access Control", "Slack")
- **Section**: a card with related fields, maps 1:1 to a MongoDB document
- **Field**: a single configurable value (string, number, boolean, string_list)

Stored values in MongoDB are **merged with the template at read time**. The UI receives the merged response and renders dynamically — it never hardcodes field definitions.

### on_update Dispatch

Sections can declare side-effects that fire after a successful update:

| Template Field | Purpose |
|----------------|---------|
| `on_update_action` | Human-readable action name (also returned to the UI) |
| `on_update_target` | Service key, resolved to a base URL via `AppConfig` |
| `on_update_endpoint` | Path on that service to POST to |

After persisting values, `ActionDispatcher` POSTs to `{base_url}{endpoint}` to notify the target service. Example: updating Slack channel restrictions triggers the RAG service to re-filter its channel list.

---

## API Endpoints

All endpoints are prefixed with `/api/admin_config/`.

| Method | Path | Description |
|--------|------|-------------|
| GET | `/config.get` | Full template merged with stored values |
| PUT | `/config.section.update` | Update one section's values |
| GET | `/access.check` | Check if a username has admin access |

### Endpoint Details

**GET /config.get** — Returns `AdminConfigResponse` (categories → sections → fields with current values).

**PUT /config.section.update** — Body: `{ sectionKey, values }`. Validates field keys against the template, persists to MongoDB, dispatches `on_update_action` if configured. Returns `{ status, on_update_action }`.

**GET /access.check** — Query: `?username=...`. Checks if the username appears in the `admin_usernames` field of the `admin_users` section. Case-insensitive comparison.

---

## Conventions

- **Pydantic models** for all data structures (request/response, template, stored entries)
- **Flask blueprints** per domain, registered in `endpoints/__init__.py`
- **Dot-notation** endpoint naming (`config.get`, `config.section.update`, `access.check`)
- **`@from_body` / `@from_query`** decorators (from `global_utils`) for request parsing
- **Singleton `AppContainer`** for dependency injection — no service locator pattern
- **Thin endpoints** — endpoints should only parse input, call the service, and format the response. No business logic in the HTTP layer.
