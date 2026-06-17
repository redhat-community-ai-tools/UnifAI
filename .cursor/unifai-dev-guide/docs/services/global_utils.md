---
service: global_utils
type: SHARED
code_root: global_utils/src/global_utils/
sections:
  quick_reference: 26
  job_description: 34
  endpoints_7: 52
  file_path_patterns: 66
  architecture: 73
  class_architecture: 95
---

# global_utils

> Shared lib (all backends)

| Field | Value |
|-------|-------|
| ID | `global_utils` |
| Type | SHARED |
| Tech Stack | Pydantic, Redis, httpx, Celery |
| Code Root | `global_utils/src/global_utils/` |
| Subtitle | Shared config, helpers, and clients — imported by all Python services |

## Quick Reference

| Item | Path |
|------|------|
| Code Root | `global_utils/src/global_utils/` |
| Shared Config | `global_utils/src/global_utils/config/config.py` |
| Package Root | `global_utils/src/global_utils/` |

## Job Description

**global_utils** is a shared Python package that lives in the monorepo at `global_utils/src/global_utils/`. It is *not* a running service — it's a library that every backend service imports as a dependency.

#### What It Provides

- **SharedConfig** — Pydantic-based config with connection strings for MongoDB, Redis, RabbitMQ, Temporal. Loads from env vars, .env files, YAML, and JSON.
- **Connection helpers** — `get_mongo_url()`, `get_redis_url()`, `get_temporal_url()`, `get_rabbitmq_url()`
- **DoclingClient / DoclingService** — shared client for local or remote document conversion
- **EmbeddingClient / EmbeddingService** — shared client for local or remote embedding generation
- **Celery app factory** — shared Celery configuration and app creation
- **Flask helpers** — common Flask setup used by all backend services
- **Utilities** — logging config, file utils, async bridge, singleton pattern, JSON Schema validation

#### Who Uses It

Every Python service: RAG, Multi Agent System (MAS), Identity, Platform Backend, Celery Workers, and Temporal Workers. They all depend on `global_utils` in their `pyproject.toml`.

## Endpoints (7)

### General

| Method | Path | Summary |
|--------|------|--------|
| CFG | `SharedConfig` | base config class with infra connection settings |
| FN | `get_mongo_url()` | builds MongoDB connection string from config |
| FN | `get_redis_url()` | builds Redis connection string |
| FN | `get_temporal_url()` | builds Temporal gRPC address |
| FN | `get_rabbitmq_url()` | builds AMQP broker URL |
| CLS | `DoclingClient / DoclingService` | document conversion |
| CLS | `EmbeddingClient / EmbeddingService` | embedding generation |

## File Path Patterns

| Category | Path |
|----------|------|
| Ports | `global_utils/src/global_utils/ports/*.py` |
| Package Root | `global_utils/src/global_utils/` |

## Architecture

#### Package Structure

- `config/` — `SharedConfig` (Pydantic BaseSettings), `ConfigManager`, multi-source loading (env, .env, YAML, JSON)
- `utils/` — `get_mongo_url()`, `get_redis_url()`, logging config, singleton, async bridge, file utils
- `redis/` — Redis client, `RedisKVStore`, server session management, session model, key constants (`identity:session:*`)
- `ports/` — Abstract interfaces (e.g. `KVStore`) shared across services
- `helpers/` — Pydantic helpers, API argument parsing
- `docling/` — Docling client/service for document conversion
- `embedding/` — Embedding client/service for vector generation
- `celery_app/` — Shared Celery app factory and configuration
- `flask/` — Common Flask setup helpers

#### How Services Use It

Each service extends `SharedConfig` with its own settings. For example, RAG's `AppConfig` adds `qdrant_ip`, `slack_bot_token`, etc. The base class provides all the shared infra connection settings.

#### Not a Deployed Service

This package is installed via `pip install -e` in development and bundled into each service's Docker image at build time. It has no CI/CD deployment of its own — it ships *inside* each service.

## Class Architecture

`global_utils` is a shared library installed in every Python service. It provides config, Redis session management, async bridging, embedding/docling HTTP clients, Celery factories, and Flask helpers.

### Key Extension Points

These are the base classes and ABCs that new code should extend or implement:

| Class | File | Layer | Implementations / Subclasses |
|-------|------|-------|------------------------------|
| `ConfigSource (ABC)` | `config/sources.py` | Config | `DotEnvSource`, `YamlSource`, `JsonSource` |
| `KVStore (ABC)` | `ports/kv_store.py` | Redis & Ports | `RedisKVStore` |

### Config

| Class | File | Role |
|-------|------|------|
| `SharedConfig` | `config/config.py` | Pydantic BaseSettings singleton: MongoDB, RabbitMQ, Temporal, Redis fields |
| `ConfigManager` | `config/manager.py` | JSON file-backed singleton config with env substitution |
| `ConfigSource (ABC)` | `config/sources.py` | Abstract load() → dict for pluggable settings sources |

- `SharedConfig` calls: `DotEnvSource`, `YamlSource`, `JsonSource`
- `SharedConfig` called by: `rag:AppConfig`, `mas:AppConfig`, `identity:AppConfig`, `platform:AppConfig`
- `ConfigSource (ABC)` called by: `DotEnvSource`, `YamlSource`, `JsonSource`

### Redis & Ports

| Class | File | Role |
|-------|------|------|
| `KVStore (ABC)` | `ports/kv_store.py` | Hexagonal port for string key-value operations with TTL |
| `RedisKVStore` | `redis/redis_kv_store.py` | Adapter: implements KVStore + hash helpers for identity sessions |
| `build_redis_client()` | `redis/client.py` | Memoized redis.Redis factory from SharedConfig |
| `UserSessionData` | `redis/session_model.py` | Pydantic model for identity Redis hash (tokens, user, expiry) |
| `get_identity_session()` | `redis/server_session.py` | Read identity hash → UserSessionData |

### Utilities

| Class | File | Role |
|-------|------|------|
| `SingletonMeta` | `utils/singleton.py` | Metaclass implementing per-process single instance |
| `AsyncBridge` | `utils/async_bridge.py` | Process-wide anyio BlockingPortal to run async from sync |
| `get_mongo_url()` | `utils/util.py` | Build MongoDB connection URL from SharedConfig |
| `get_redis_url()` | `utils/util.py` | Build Redis connection URL |
| `get_rabbitmq_url()` | `utils/util.py` | Build AMQP broker URL |
| `json_schema_model()` | `utils/util.py` | Generate Pydantic model from JSON Schema at runtime |

- `SingletonMeta` called by: `mas:AppContainer`, `mas:ElementRegistry`, `AsyncBridge`
- `AsyncBridge` calls: `anyio`, `threading`
- `AsyncBridge` called by: `mas:McpProvider`, `mas:A2AAgentNode`, `mas:CustomAgentNode`
- `get_mongo_url()` calls: `SharedConfig`
- `get_mongo_url()` called by: `rag:AppContainer`, `mas:AppContainer`, `identity:create_app()`, `platform:AppContainer`, `CeleryApp`

### Docling & Embedding Clients

| Class | File | Role |
|-------|------|------|
| `DoclingClient` | `docling/client.py` | Sync httpx transport: async job submit/poll/fetch for document conversion |
| `DoclingService` | `docling/service.py` | Validates inputs, calls client, validates response |
| `EmbeddingClient` | `embedding/client.py` | httpx POST /v1/embeddings with truncate flag |
| `EmbeddingService` | `embedding/service.py` | Validates text list, maps response to vectors |

### Celery & Flask

| Class | File | Role |
|-------|------|------|
| `CeleryApp` | `celery_app/init.py` | Singleton wrapping celery.Celery: RabbitMQ broker, Mongo backend |
| `send_task()` | `celery_app/helpers.py` | Send named task to Celery queue |
| `RequestRules` | `flask/request_rules.py` | Flask before/after request hooks (size cap, headers) |
| `require_identity_session()` | `flask/decorators.py` | Decorator: validates identity session from Redis |

- `RequestRules` called by: `rag:AppContainer`, `mas:AppContainer`, `identity:create_app()`, `platform:AppContainer`

---

*Source: `js/data/services/global_utils.js`* | *Classes: `js/data-classes/global_utils.js`*
