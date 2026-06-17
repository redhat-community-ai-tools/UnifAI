---
service: platform
type: APP
code_root: backend/
sections:
  quick_reference: 27
  connections: 37
  job_description: 45
  endpoints_5: 60
  file_path_patterns: 72
  architecture: 82
  class_architecture: 98
---

# Platform Backend

> Admin configuration service

| Field | Value |
|-------|-------|
| ID | `platform` |
| Type | APP |
| Tech Stack | Flask, MongoDB |
| Code Root | `backend/` |
| Subtitle | Flask • Port 8005 • /api4 |

## Quick Reference

| Item | Path |
|------|------|
| Code Root | `backend/` |
| Composition Root | `backend/core/app_container.py` |
| Flask Factory | `backend/api/flask/flask_app.py` |
| App Config | `backend/config/app_config.py` |
| Entry Points | `backend/run/dev.py`, `backend/run/wsgi.py` |

## Connections

**Incoming:**
- `ui` → `platform` *(/api4)*

**Outgoing:**
- `platform` → `mongodb` *(config)*

## Job Description

The **Platform Backend** is a small, focused service for centralized admin configuration. Think of it as the "settings API" for the whole system.

#### What It Does

- Stores admin configuration sections in MongoDB (template-driven)
- Serves merged config (template defaults + saved overrides)
- On config update, can **dispatch side-effects** to other services via HTTP POST
- Enforces admin access via `X-Username` / `X-User-Id` headers

#### ActionDispatcher

When a config section has `on_update_target` and `on_update_endpoint`, saving triggers an HTTP POST to the target service. Currently only RAG is wired.

## Endpoints (5)

### General

| Method | Path | Summary |
|--------|------|--------|
| GET | `/api/admin_config/config.get` | merged template + DB |
| PUT | `/api/admin_config/config.section.update` | admin only |
| GET | `/api/admin_config/access.check?username=` |  |
| GET | `/api/health/` |  |
| GET | `/api/health/version` |  |

## File Path Patterns

| Category | Path |
|----------|------|
| Endpoints | `backend/api/flask/endpoints/*.py` |
| Composition Root | `backend/core/app_container.py` |
| Flask Factory | `backend/api/flask/flask_app.py` |
| App Config | `backend/config/app_config.py` |
| Mongo Adapters | `backend/admin_config/repository/mongo_repository.py` |

## Architecture

#### Structure

- `core/app_container.py` — DI container, wires Mongo + ActionDispatcher
- `admin_config/service.py` — AdminConfigService: merge, update, dispatch
- `admin_config/repository/` — MongoAdminConfigRepository
- `admin_config/template.py` — config section definitions
- `admin_config/action_dispatcher.py` — HTTP POST to target services
- `api/flask/` — Flask app + endpoint blueprints

#### MongoDB

- Database: `config`, Collection: `admin_config`
- Unique index on `key`

## Class Architecture

Platform Backend is a small admin config service. It uses `AppContainer` (singleton) to wire MongoDB + `ActionDispatcher` + `AdminConfigService`.

### Key Extension Points

These are the base classes and ABCs that new code should extend or implement:

| Class | File | Layer | Implementations / Subclasses |
|-------|------|-------|------------------------------|
| `AdminConfigRepository (ABC)` | `admin_config/repository/repository.py` | Admin Config Domain | `MongoAdminConfigRepository`, `AdminConfigService` |

### Bootstrap

| Class | File | Role |
|-------|------|------|
| `AppContainer` | `core/app_container.py` | Singleton DI: MongoClient, repos, ActionDispatcher, AdminConfigService |

- `AppContainer` calls: `MongoAdminConfigRepository`, `ActionDispatcher`, `AdminConfigService`, `AppConfig`
- `AppContainer` called by: `entrypoint`

### Config

| Class | File | Role |
|-------|------|------|
| `AppConfig` | `config/app_config.py` | Platform settings (Mongo names, rag_url, admin_users, port) |

### Admin Config Domain

| Class | File | Role |
|-------|------|------|
| `AdminConfigService` | `admin_config/service.py` | Merge template + DB; validate/update sections; optional dispatch |
| `ActionDispatcher` | `admin_config/action_dispatcher.py` | POST to target services after config save |
| `AdminConfigRepository (ABC)` | `admin_config/repository/repository.py` | Port: get(key)/set(entry) for config entries |
| `MongoAdminConfigRepository` | `admin_config/repository/mongo_repository.py` | Mongo implementation with unique index on key |

- `AdminConfigService` calls: `AdminConfigRepository`, `ActionDispatcher`, `AdminConfigTemplate`
- `AdminConfigService` called by: `AppContainer`, `HTTP: /admin_config/`

### Models

| Class | File | Role |
|-------|------|------|
| `AdminConfigTemplate` | `admin_config/models.py` | Static template tree: categories → sections → fields |
| `AdminConfigEntry` | `admin_config/models.py` | Mongo document: section key + value dict + timestamp |
| `AdminConfigResponse` | `admin_config/models.py` | Root DTO: merged template + stored values for API |
| `FieldDefinition` | `admin_config/models.py` | Schema for one configurable field |
| `SectionDefinition` | `admin_config/models.py` | Group of fields + optional on_update hooks |

- `AdminConfigResponse` calls: `CategoryValue`, `SectionValue`, `FieldValue`
- `AdminConfigResponse` called by: `AdminConfigService`

---

*Source: `js/data/services/platform.js`* | *Classes: `js/data-classes/platform.js`*
