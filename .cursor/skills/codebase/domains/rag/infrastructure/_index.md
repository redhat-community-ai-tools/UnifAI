---
name: rag-infrastructure
scope: Flask blueprints, Mongo repositories, Qdrant client, Celery, source connectors
parent: ../_index.md
when_to_load: Working on adapters, repositories, or external integrations in rag/
---

# RAG Infrastructure Component

Outer ring — implements ports defined by core components. ~59 files covering Flask HTTP, MongoDB, Qdrant, Celery, and source connectors.

## Flask API (8 Blueprints, 27 endpoints)

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

## MongoDB (3 databases, 7+ collections)

| Database | Collection | Adapter |
|----------|-----------|---------|
| `pipeline_monitoring` | `pipelines` | `MongoPipelineRepository` |
| `pipeline_monitoring` | `metrics` | `MongoMonitoringRepository` |
| `pipeline_monitoring` | `errors` | `MongoMonitoringRepository` |
| `pipeline_monitoring` | `logs` | `MongoMonitoringRepository` |
| `data_sources` | `sources` | `MongoDataSourceRepository` |
| `data_sources` | `slack_channels` | `MongoSlackChannelRepository` |
| `users` | `terms_user_approval` | `MongoTermsApprovalRepository` |

## Port → Adapter Wiring

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

## Celery Tasks

| Task | File | Queue |
|------|------|-------|
| `execute_pipeline_task` | `celery/workers/pipeline_tasks.py` | `document_queue` / `slack_queue` |
| `process_slack_events_task` | `celery/workers/slack_event_tasks.py` | `slack_events_queue` (3 retries) |

## Boundaries

- Implements ports from `core/` — pure I/O translation, no business logic
- Each adapter catches infrastructure-specific exceptions and wraps in domain exceptions
- Adapters are stateless; connection state managed by client libraries
