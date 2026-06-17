---
name: global-utils-knowledge
description: >-
  Domain knowledge for the global_utils shared Python library. Provides
  cross-service utilities: config, Redis, ports, helpers, embedding, Flask,
  and Celery app setup. Use when working on files under global_utils/.
paths: global_utils/**
---

# Global Utils Knowledge System

Shared Python package at `global_utils/src/global_utils/`. Not a running service — installed as a dependency by every backend service (MAS, RAG, Identity, Platform, Celery, Temporal Worker).

## Module Routing

| Module | Path | Key Exports | Description |
|--------|------|-------------|-------------|
| `config` | `config/` | `SharedConfig`, `ConfigManager`, `ConfigSource` | Pydantic BaseSettings, multi-source loading (env, .env, YAML, JSON) |
| `utils` | `utils/` | `get_mongo_url`, `get_redis_url`, `get_temporal_url`, `get_rabbitmq_url`, `SingletonMeta`, `AsyncBridge` | Connection helpers, patterns |
| `redis` | `redis/` | `RedisKVStore`, `build_redis_client`, `get_identity_session`, `UserSessionData` | Redis client, session management |
| `ports` | `ports/` | `KVStore` | Shared abstract interfaces |
| `helpers` | `helpers/` | API arg parsing, decorators | Pydantic helpers, `@from_body` / `@from_query` |
| `docling` | `docling/` | `DoclingClient`, `DoclingService` | Document conversion (local/remote) |
| `embedding` | `embedding/` | `EmbeddingClient`, `EmbeddingService` | Embedding generation (local/remote) |
| `celery_app` | `celery_app/` | `CeleryApp`, `send_task` | Shared Celery factory and config |
| `flask` | `flask/` | `RequestRules`, `require_identity_session` | Common Flask setup, auth decorators |

## Key Classes

| Class | File | Role |
|-------|------|------|
| `SharedConfig` | `config/config.py` | Pydantic BaseSettings singleton: MongoDB, RabbitMQ, Temporal, Redis fields |
| `ConfigManager` | `config/manager.py` | JSON file-backed singleton config with env substitution |
| `ConfigSource` (ABC) | `config/sources.py` | Abstract `load()` → dict for pluggable sources |
| `KVStore` (ABC) | `ports/kv_store.py` | Hexagonal port for key-value operations with TTL |
| `RedisKVStore` | `redis/redis_kv_store.py` | Adapter: implements KVStore + hash helpers for identity sessions |
| `SingletonMeta` | `utils/singleton.py` | Metaclass for per-process single instance |
| `AsyncBridge` | `utils/async_bridge.py` | Process-wide anyio BlockingPortal to run async from sync |
| `CeleryApp` | `celery_app/init.py` | Singleton Celery with RabbitMQ broker + Mongo backend |
| `RequestRules` | `flask/request_rules.py` | Flask before/after request hooks (size cap, headers) |

## Config Inheritance Pattern

```
SharedConfig (global_utils)
    ├── AppConfig (rag)       — adds qdrant_ip, embedding settings, etc.
    ├── AppConfig (mas)       — adds engine, temporal, redis settings
    ├── AppConfig (identity)  — adds Keycloak, session, team settings
    └── AppConfig (platform)  — adds Mongo names, rag_url, admin_users
```

## Landmarks

| Landmark | Location |
|----------|----------|
| Package root | `global_utils/src/global_utils/` |
| Package exports | `global_utils/src/global_utils/__init__.py` |
| Shared config | `global_utils/src/global_utils/config/config.py` |
| Redis client factory | `global_utils/src/global_utils/redis/client.py` |
| Shared ports | `global_utils/src/global_utils/ports/` |

## Dev-Guide Facts

For class architecture, export catalogs, and module details:
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/global_utils.md`
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → global_utils`
- **Code → doc routing:** `.cursor/unifai-dev-guide/guide-index.yaml` (maps `global_utils/src/global_utils/**` to global_utils.md)

## Cross-Service Impact

Changes to `global_utils` affect ALL backend services. Exercise extreme caution:
- Backward compatibility is mandatory
- New required parameters must have defaults
- Deprecation before removal
- Every dependency added here becomes a transitive dependency of all services

## Domain Rules

Domain-specific rules for the shared library. For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

### 1. Backward Compatibility Is Mandatory

All public APIs in global_utils are consumed by multiple services. Any change
to function signatures, class interfaces, or behavior must be backward-compatible.
New parameters require default values. Breaking changes require a deprecation cycle.

---

### 2. No Service-Specific Logic

global_utils must remain generic. It provides infrastructure utilities, not
business logic. If logic is specific to one service, it belongs in that service.

---

### 3. Minimal External Dependencies

Every dependency added to global_utils becomes a transitive dependency of all
services. Minimize external packages. Prefer stdlib solutions where adequate.

---

### 4. Config Module Is the Single Source

All environment variable resolution for shared concerns goes through the config module.
Services extend `SharedConfig` with their own settings — they don't read `os.environ`
directly for infrastructure connection strings.

---

### 5. Port Interfaces Are Minimal

Ports in `global_utils/ports/` define minimal abstract contracts shared across services.
Keep them focused (ISP). Service-specific ports belong in the service's own domain layer.

---

### 6. Redis Key Namespace Convention

All Redis keys must be namespaced by service: `identity:{key}`, `mas:{key}`.
`global_utils/redis/` provides the client and helpers but does not own key schemas —
each service defines its own key patterns.

---

### Established Patterns — Global Utils

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `SingletonMeta` metaclass for process-wide singletons | `utils/singleton.py` — used by MAS/Backend `AppContainer`, `ElementRegistry`, `ActionRegistry` | Multi-entry-point services need guaranteed single instances; first-construction-wins |
| `AsyncBridge` global accessor (`get_async_bridge()`) | `utils/async_bridge.py` — consumed from MAS domain elements, tools, actions | Sync graph nodes calling async SDKs need a process-wide anyio portal; injection would thread through every factory |
| `SharedConfig.get_instance()` ambient singleton | `config/config.py` — all services call at bootstrap | Pydantic BaseSettings with cached instance; monorepo convention for config loading |
| `CeleryApp()` singleton in task decorators | `celery_app/init.py` — used in RAG task files | Worker entry point needs a single Celery app; `@app.task` decorator requires module-level access |
