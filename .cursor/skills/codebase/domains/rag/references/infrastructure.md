# Infrastructure Component

Outer ring — implements ports defined by core components. ~59 files covering Flask HTTP, MongoDB, Qdrant, Celery, and source connectors.

## Architecture

### Flask API (8 Blueprints, 27 endpoints)

| Blueprint | File | Prefix | Key routes |
|-----------|------|--------|------------|
| `health_bp` | `http/health.py` | `/api/health/` | Liveness, version, readiness |
| `vector_bp` | `http/vector.py` | `/api/vector/` | Chunk counts |
| `settings_bp` | `http/settings.py` | `/api/settings/` | Umami config |
| `pipelines_bp` | `http/pipelines.py` | `/api/pipelines/` | Trigger embedding |
| `data_sources_bp` | `http/data_sources.py` | `/api/data_sources/` | Source CRUD |
| `docs_bp` | `http/docs.py` | `/api/docs/` | Upload, validate, search |
| `slack_bp` | `http/slack.py` | `/api/slack/` | Channels, search, events |
| `terms_approval_bp` | `http/terms_approval.py` | `/api/terms_approval/` | User approval |

Registration: `rag/infrastructure/http/blueprints.py`

### MongoDB (3 databases, 7+ collections)

| Database | Collection | Adapter |
|----------|-----------|---------|
| `pipeline_monitoring` | `pipelines` | `MongoPipelineRepository` |
| `pipeline_monitoring` | `metrics` | `MongoMonitoringRepository` |
| `pipeline_monitoring` | `errors` | `MongoMonitoringRepository` |
| `pipeline_monitoring` | `logs` | `MongoMonitoringRepository` |
| `data_sources` | `sources` | `MongoDataSourceRepository` |
| `data_sources` | `slack_channels` | `MongoSlackChannelRepository` |
| `users` | `terms_user_approval` | `MongoTermsApprovalRepository` |

### Port → Adapter Wiring

| Port | Adapter | Tech |
|------|---------|------|
| `VectorRepository` | `QdrantVectorRepository` | Qdrant |
| `PipelineRepository` | `MongoPipelineRepository` | MongoDB |
| `DataSourceRepository` | `MongoDataSourceRepository` | MongoDB |
| `MonitoringRepository` | `MongoMonitoringRepository` | MongoDB |
| `SlackChannelRepository` | `MongoSlackChannelRepository` | MongoDB |
| `TermsApprovalRepository` | `MongoTermsApprovalRepository` | MongoDB |
| `EmbeddingPort` | `Local/RemoteEmbeddingAdapter` | sentence-transformers / HTTP |
| `DocumentConverterPort` | `Local/RemoteDoclingAdapter` | Docling / HTTP |
| `PipelineTaskDispatcher` | `CeleryPipelineDispatcher` | RabbitMQ |
| `SlackEventDispatcher` | `CelerySlackEventDispatcher` | RabbitMQ |
| `DataConnector` | `DocumentConnector` / `SlackConnector` | Filesystem / Slack API |
| `ContentChunker` | `PDFChunkerStrategy` / `SlackChunkerStrategy` | LangChain splitters |

### Celery Tasks

| Task | File | Queue |
|------|------|-------|
| `execute_pipeline_task` | `celery/workers/pipeline_tasks.py` | `document_queue` / `slack_queue` |
| `process_slack_events_task` | `celery/workers/slack_event_tasks.py` | `slack_events_queue` (3 retries) |

## How to Extend

### Adding a New Flask Endpoint

1. Add route to the appropriate blueprint under `infrastructure/http/`
2. Access services via app container (wired at startup)
3. Keep endpoint thin: parse request → call domain service → format response
4. Register blueprint in `blueprints.py` if creating a new blueprint

### Adding a New Mongo Repository Adapter

1. Define or extend the port ABC in `core/`
2. Implement adapter in `infrastructure/mongo/` implementing exactly one port
3. Wire in `app_container.py` via `@lru_cache` property
4. Catch infrastructure exceptions and wrap in domain exceptions

### Adding a New Celery Task

1. Create thin task in `infrastructure/celery/workers/` — resolve deps from container, delegate to domain service
2. Register queue in Celery app config
3. Add dispatcher adapter if async dispatch is needed from core

## Cross-Component Contracts

### Infrastructure ← Bootstrap (wiring)

- `app_container.py` instantiates all adapters and injects into core services via `@lru_cache`
- Configuration resolved from `AppConfig` (extends `SharedConfig`) at startup
- Conditional wiring for local/remote adapters via `factories.py`:
  - `DocumentConverterFactory` → local or remote Docling
  - `EmbeddingPortFactory` → local or remote embedding
  - `VectorRepositoryFactory` → Qdrant from config

### Infrastructure → External Systems

| External System | Adapter | Connection | Failure Mode |
|----------------|---------|------------|-------------|
| MongoDB | `Mongo*Repository` (5) | TCP via pymongo | Service fails to start |
| Qdrant | `QdrantVectorRepository` | HTTP `qdrant_ip:qdrant_port` | Search unavailable |
| RabbitMQ | `CeleryPipelineDispatcher` | AMQP via Celery | Pipeline dispatch fails |
| Embedding API | `RemoteEmbeddingAdapter` | HTTP `/v1/embeddings` | Pipeline stages fail |
| Docling API | `RemoteDoclingAdapter` | HTTP `/v1/convert/*` | Document conversion fails |
| Slack API | `SlackConnector` | HTTP (Slack Web API) | Source-specific errors |

### Port Implementation Rules

- Each adapter implements exactly one port (ABC)
- Adapters catch infrastructure-specific exceptions → wrap in domain exceptions
- No domain logic in adapters — pure I/O translation
- Adapters are stateless (connection state managed by client libraries)
- Flask endpoints are thin: parse request → call service → format response

## Established Patterns

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Celery tasks importing from `bootstrap.app_container` | `celery/workers/pipeline_tasks.py`, `slack_event_tasks.py` | Tasks are driving adapters; 3-line delegate pattern |
| LangChain in chunker adapters | `sources/document/chunker.py`, `sources/slack/chunker.py` | Chunkers implement `ContentChunker` port; core has ABC only |
| Lazy imports in factory `__init__.py` | Embedding/Docling adapter packages | Prevents heavy deps loading in remote mode |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Mongo collection schema | Repository adapter + core models | Adapter maps DB ↔ domain |
| Qdrant client config | `VectorRepositoryFactory`, AppConfig | Connection wired at bootstrap |
| Celery queue name | Dispatcher adapter + worker config | Queue names must match |
| Flask blueprint prefix | UI API routes, reverse proxy config | Prefix is part of public API |

## Boundaries

- Implements ports from `core/` — pure I/O translation, no business logic
- Each adapter catches infrastructure-specific exceptions and wraps in domain exceptions
- Adapters are stateless; connection state managed by client libraries
