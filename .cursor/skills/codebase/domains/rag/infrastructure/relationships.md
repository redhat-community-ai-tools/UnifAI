---
name: rag-infrastructure-relationships
scope: Port-adapter wiring and external system contracts
parent: _index.md
---

# Infrastructure Relationships

## Infrastructure ← Bootstrap (wiring)

- `app_container.py` instantiates all adapters and injects into core services via `@lru_cache`
- Configuration resolved from `AppConfig` (extends `SharedConfig`) at startup
- Conditional wiring for local/remote adapters via `factories.py`:
  - `DocumentConverterFactory` → local or remote Docling
  - `EmbeddingPortFactory` → local or remote embedding
  - `VectorRepositoryFactory` → Qdrant from config

## Infrastructure → External Systems

| External System | Adapter | Connection | Failure Mode |
|----------------|---------|------------|-------------|
| MongoDB | `Mongo*Repository` (5) | TCP via pymongo | Service fails to start |
| Qdrant | `QdrantVectorRepository` | HTTP `qdrant_ip:qdrant_port` | Search unavailable |
| RabbitMQ | `CeleryPipelineDispatcher` | AMQP via Celery | Pipeline dispatch fails |
| Embedding API | `RemoteEmbeddingAdapter` | HTTP `/v1/embeddings` | Pipeline stages fail |
| Docling API | `RemoteDoclingAdapter` | HTTP `/v1/convert/*` | Document conversion fails |
| Slack API | `SlackConnector` | HTTP (Slack Web API) | Source-specific errors |

## Port Implementation Rules

- Each adapter implements exactly one port (ABC)
- Adapters catch infrastructure-specific exceptions → wrap in domain exceptions
- No domain logic in adapters — pure I/O translation
- Adapters are stateless (connection state managed by client libraries)
- Flask endpoints are thin: parse request → call service → format response
