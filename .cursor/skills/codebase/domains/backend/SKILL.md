---
name: backend-knowledge
description: >-
  Domain knowledge for the Platform Backend service. Admin config, platform API,
  and core orchestration. Use when working on files under backend/.
paths: backend/**
---

# Backend Knowledge System

Admin configuration service. Stores platform-wide settings in MongoDB, serves merged config (template defaults + saved overrides), and dispatches side-effects on update.

## Component Routing

| Path prefix | Component | Description |
|-------------|-----------|-------------|
| `admin_config/service.py` | Admin Config Service | Merge template + DB; validate/update; optional dispatch |
| `admin_config/repository/` | Persistence | `AdminConfigRepository` (ABC) + `MongoAdminConfigRepository` |
| `admin_config/models.py` | Domain Models | `AdminConfigTemplate`, `AdminConfigEntry`, `AdminConfigResponse` |
| `admin_config/template.py` | Template | Config section definitions (categories → sections → fields) |
| `admin_config/action_dispatcher.py` | Action Dispatcher | HTTP POST to target services after config save |
| `api/flask/endpoints/` | API Layer | Flask blueprints: admin_config, health |
| `core/app_container.py` | Bootstrap | Singleton DI: MongoClient, repos, dispatcher, service |
| `config/app_config.py` | Config | `AppConfig(SharedConfig)` with Mongo names, admin_users |
| `run/` | Entry Points | `dev.py`, `wsgi.py` |

## Landmarks

| Landmark | Location |
|----------|----------|
| Composition root | `backend/core/app_container.py` |
| Flask factory | `backend/api/flask/flask_app.py` |
| App config | `backend/config/app_config.py` |
| Endpoint registration | `backend/api/flask/endpoints/__init__.py` |
| Admin config domain | `backend/admin_config/` |

## Key Classes

| Class | File | Role |
|-------|------|------|
| `AppContainer` | `core/app_container.py` | Singleton DI: MongoClient, repos, ActionDispatcher, AdminConfigService |
| `AdminConfigService` | `admin_config/service.py` | Merge template + DB; validate/update sections; optional dispatch |
| `ActionDispatcher` | `admin_config/action_dispatcher.py` | POST to target services after config save |
| `AdminConfigRepository` (ABC) | `admin_config/repository/repository.py` | Port: get(key)/set(entry) |
| `MongoAdminConfigRepository` | `admin_config/repository/mongo_repository.py` | Mongo adapter, unique index on `key` |

## Endpoints (5)

| Method | Path | Summary |
|--------|------|---------|
| GET | `/api/admin_config/config.get` | Merged template + DB config |
| PUT | `/api/admin_config/config.section.update` | Admin-only update |
| GET | `/api/admin_config/access.check` | Check admin access |
| GET | `/api/health/` | Liveness |
| GET | `/api/health/version` | Version |

## MongoDB

| Database | Collection | Adapter |
|----------|-----------|---------|
| `config` | `admin_config` | `MongoAdminConfigRepository` (unique index on `key`) |

## Dev-Guide Facts

For class architecture, endpoint details, and domain model documentation:
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/platform.md`
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → platform`
- **Code → doc routing:** `.cursor/unifai-dev-guide/guide-index.yaml` (maps `backend/**` to platform.md)

## ActionDispatcher

When a config section has `on_update_target` and `on_update_endpoint`,
saving triggers an HTTP POST to the target service. Currently only RAG is wired.

## Domain Rules

Domain-specific rules for the platform backend. For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

### 1. Admin Config Isolation

Admin configuration is a distinct bounded context. It has its own domain models,
services, and persistence. Other services consume admin config via API calls or
shared config, never by importing backend internals.

**Documented exception**: MAS's `MongoAdminConfigReader` (`multi-agent/adapters/outbound/mongo/admin_config_reader.py`)
reads the `config.admin_config` collection directly and read-only, to answer
`is_admin(username)` without a network round-trip per request. It never writes to
this collection — writes remain exclusively through `AdminConfigService`
(`config.section.update`). This is a narrow, intentional exception, not backend-internals
importing; see the mirrored entry in `domains/multi-agent/references/adapters.md`.

---

### 2. Platform-Level Concerns Only

The backend service handles platform-wide operations (admin config, feature flags,
system health). Service-specific business logic belongs in its own service (MAS, RAG, etc.),
not in the platform backend.

---

### 3. Template-Driven Config Schema

Config sections are defined in `admin_config/template.py` as static definitions.
The service merges template defaults with stored overrides at read time.
New config sections are added by extending the template — not by modifying service logic.

---

### 4. Side-Effect Dispatch

Config updates can trigger side-effects via `ActionDispatcher`. The dispatch target
and endpoint are declared in the template section definition (`on_update_target`,
`on_update_endpoint`). No ad-hoc HTTP calls from the service layer.

---

### Established Patterns — Platform Backend

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `ActionDispatcher` with direct `requests.post()` — no port ABC | `admin_config/action_dispatcher.py` | Single outbound integration (RAG only); port abstraction for one consumer is over-engineering |
| Flat package layout (no `domain/`, `ports/`, `adapters/` split) | `admin_config/`, `api/flask/`, `core/` | Service has ~10 files total; hex folder ceremony would add noise without benefit |
| `current_app.container.admin_config_service` access in endpoints | `api/flask/endpoints/*.py` | Standard Flask composition — no DI framework; container is wired at startup |
| `SingletonMeta` on `AppContainer` | `core/app_container.py` | Process-wide singleton for Flask entry point; same pattern as MAS |
| Gateway-trust auth via `X-Username` / `X-User-Id` headers | Flask endpoints | Admin-only service behind gateway; no need for full Identity auth stack |
| MAS reads `config.admin_config` directly (read-only) instead of calling an API | `multi-agent/adapters/outbound/mongo/admin_config_reader.py` | Avoids a per-request network round-trip for the `is_admin` gate; write path is unaffected — still exclusively `AdminConfigService` |
