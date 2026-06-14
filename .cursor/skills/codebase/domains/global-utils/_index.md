---
name: global-utils-library
scope: Shared Python library used by all backend services
parent: ../SKILL.md
when_to_load: Any work touching global_utils/
---

# Global Utils

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
- **Service doc:** `unifai-dev-guide/docs/services/global_utils.md`
- **Source map:** `unifai-dev-guide/source-map.yaml → global_utils`
- **Code → doc routing:** `unifai-dev-guide/guide-index.yaml` (maps `global_utils/src/global_utils/**` to global_utils.md)

## Cross-Service Impact

Changes to `global_utils` affect ALL backend services. Exercise extreme caution:
- Backward compatibility is mandatory
- New required parameters must have defaults
- Deprecation before removal
- Every dependency added here becomes a transitive dependency of all services
