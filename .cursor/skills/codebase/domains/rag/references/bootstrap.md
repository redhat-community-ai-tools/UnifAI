# Bootstrap Component

Composition root — wires all ~40 singletons, creates the Flask app, and registers blueprints.

## Architecture

### Key Files

| File | Role |
|------|------|
| `bootstrap/app_container.py` | Composition root: ~640 lines, `@lru_cache` singletons |
| `bootstrap/flask_app.py` | Flask factory: loads config, builds app, registers blueprints |
| `bootstrap/factories.py` | Local/remote adapter switching based on config flags |
| `config/app_config.py` | `AppConfig(SharedConfig)` with ~25 settings |

### Factory Classes

| Factory | Decides between |
|---------|----------------|
| `DocumentConverterFactory` | `LocalDoclingAdapter` ↔ `RemoteDoclingAdapter` |
| `DocumentConnectorFactory` | Builds `DocumentConnector` with chosen converter |
| `EmbeddingPortFactory` | `LocalEmbeddingAdapter` ↔ `RemoteEmbeddingAdapter` |
| `EmbeddingGeneratorFactory` | Wraps `EmbeddingPort` in `DefaultEmbeddingGenerator` |
| `VectorRepositoryFactory` | Builds `QdrantVectorRepository` from config |

### Key Config Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `port` | 13456 | Flask server port |
| `use_remote_docling` | false | Local vs remote document conversion |
| `use_remote_embedding` | false | Local vs remote embedding generation |
| `qdrant_ip` / `qdrant_port` | localhost:6333 | Qdrant connection |
| `embedding_dim` | 384 | Vector dimension |

### Wiring Pattern

Constructor injection only. Services receive dependencies as constructor parameters.
No service instantiates its own infrastructure dependencies.
No global state, no service locator.

## How to Extend

### Adding a New Wired Service

1. Define the service in `core/` with constructor-injected dependencies
2. Add `@lru_cache` property method in `app_container.py` that builds the dependency graph
3. Expose as a container attribute for Flask endpoints and Celery tasks
4. If the service needs a new adapter, add factory method in `factories.py`

### Adding a New Config Parameter

1. Add typed field to `config/app_config.py` with default
2. Use in `app_container.py` or relevant factory: `AppConfig.get_instance().<field>`
3. For local/remote switching, add `use_remote_*` flag and branch in factory

### Local / Remote Adapter Switching

```python
# Pattern in factories.py — lazy imports prevent heavy deps in remote mode
if config.use_remote_embedding:
    from infrastructure.embedding.embedders.remote_embedding_adapter import RemoteEmbeddingAdapter
    return RemoteEmbeddingAdapter(...)
else:
    from infrastructure.embedding.embedders.local_embedding_adapter import LocalEmbeddingAdapter
    return LocalEmbeddingAdapter(...)
```

## Cross-Component Contracts

### Bootstrap → All Components

- `app_container.py` instantiates all adapters and injects into core services via `@lru_cache`
- Configuration resolved from `AppConfig` (extends `SharedConfig`) at startup
- `get_pipeline_handler()` registry maps `"SLACK"` / `"DOCUMENT"` → cached factory functions

### Bootstrap → Infrastructure (conditional wiring)

- `DocumentConverterFactory` → local or remote Docling
- `EmbeddingPortFactory` → local or remote embedding
- `VectorRepositoryFactory` → Qdrant from config

### Bootstrap → Entry Points

- `flask_app.py` builds Flask app, attaches container, registers blueprints
- Celery workers import container directly (established pattern for driving adapters)
- `clear_all_caches()` on container for test isolation

## Established Patterns

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `@lru_cache` singleton container | `bootstrap/app_container.py` (~640 lines, ~40 singletons) | Composition root — explicit function-call graphs; `clear_all_caches()` for tests |
| Factory `if config.use_remote_*` + lazy imports | `bootstrap/factories.py` | Encapsulated local/remote switching; prevents torch/docling loading in remote mode |
| `get_pipeline_handler()` registry dict | `app_container.py` | Handler routing by source type; dictionary acts as factory |
| `AppConfig.get_instance()` ambient singleton | `bootstrap/`, `infrastructure/http/`, `infrastructure/celery/app.py` | Pydantic BaseSettings — monorepo convention; bootstrap reads once, never from core |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Service constructor deps | `app_container.py` wiring | Injection graph is centralized |
| New adapter type | `factories.py` + config field | Factory selects implementation |
| Pipeline handler registry | Data-sources plugin set | Handler map must cover all source types |
| `@lru_cache` parameters | Test fixtures calling `clear_all_caches()` | Cache keys affect test isolation |

## Boundaries

**Owns:** object graph assembly, adapter instantiation, config reading, Flask app creation.
**Does NOT own:** business logic, domain rules, adapter implementation details.
Container is the only layer that imports both `core/` and `infrastructure/`.
