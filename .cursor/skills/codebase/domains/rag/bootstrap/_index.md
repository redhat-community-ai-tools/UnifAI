---
name: rag-bootstrap
scope: App container, factories, config, and startup wiring
parent: ../_index.md
when_to_load: Working on startup, configuration, or dependency wiring in rag/
---

# RAG Bootstrap Component

Composition root — wires all ~40 singletons, creates the Flask app, and registers blueprints.

## Key Files

| File | Role |
|------|------|
| `bootstrap/app_container.py` | Composition root: ~640 lines, `@lru_cache` singletons |
| `bootstrap/flask_app.py` | Flask factory: loads config, builds app, registers blueprints |
| `bootstrap/factories.py` | Local/remote adapter switching based on config flags |
| `config/app_config.py` | `AppConfig(SharedConfig)` with ~25 settings |

## Factory Classes

| Factory | Decides between |
|---------|----------------|
| `DocumentConverterFactory` | `LocalDoclingAdapter` ↔ `RemoteDoclingAdapter` |
| `DocumentConnectorFactory` | Builds `DocumentConnector` with chosen converter |
| `EmbeddingPortFactory` | `LocalEmbeddingAdapter` ↔ `RemoteEmbeddingAdapter` |
| `EmbeddingGeneratorFactory` | Wraps `EmbeddingPort` in `DefaultEmbeddingGenerator` |
| `VectorRepositoryFactory` | Builds `QdrantVectorRepository` from config |

## Key Config Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| `port` | 13456 | Flask server port |
| `use_remote_docling` | false | Local vs remote document conversion |
| `use_remote_embedding` | false | Local vs remote embedding generation |
| `qdrant_ip` / `qdrant_port` | localhost:6333 | Qdrant connection |
| `embedding_dim` | 384 | Vector dimension |

## Wiring Pattern

Constructor injection only. Services receive dependencies as constructor parameters.
No service instantiates its own infrastructure dependencies.
No global state, no service locator.
