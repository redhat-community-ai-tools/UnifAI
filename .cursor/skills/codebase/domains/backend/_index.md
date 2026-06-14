---
name: backend-service
scope: Platform Backend — admin config and platform API
parent: ../SKILL.md
when_to_load: Any work touching backend/
---

# Platform Backend

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
- **Service doc:** `unifai-dev-guide/docs/services/platform.md`
- **Source map:** `unifai-dev-guide/source-map.yaml → platform`
- **Code → doc routing:** `unifai-dev-guide/guide-index.yaml` (maps `backend/**` to platform.md)

## ActionDispatcher

When a config section has `on_update_target` and `on_update_endpoint`,
saving triggers an HTTP POST to the target service. Currently only RAG is wired.
