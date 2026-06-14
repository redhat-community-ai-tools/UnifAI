---
service: rag
type: APP
code_root: rag/
sections:
  quick_reference: 30
  connections: 40
  features: 51
  job_description: 57
  endpoints_27: 115
  port_abstractions_21: 179
  file_path_patterns: 205
  architecture: 217
  class_architecture: 333
---

# RAG

> Document & vector search

| Field | Value |
|-------|-------|
| ID | `rag` |
| Type | APP |
| Tech Stack | Flask, Celery, Qdrant, MongoDB, sentence-transformers, Docling |
| Code Root | `rag/` |
| Shares Codebase With | celery |
| Subtitle | Flask • Port 13457 • Celery pipelines |

## Quick Reference

| Item | Path |
|------|------|
| Code Root | `rag/` |
| Composition Root | `rag/bootstrap/app_container.py` |
| Flask Factory | `rag/bootstrap/flask_app.py` |
| App Config | `rag/config/app_config.py` |
| Shared Config | `global_utils/src/global_utils/config/config.py` |

## Connections

**Incoming:**
- `ui` → `rag` *(/api1)*
- `slack` → `rag` *(paused)*

**Outgoing:**
- `rag` → `rabbitmq` *(enqueue)*
- `rag` → `mongodb` *(metadata)*
- `rag` → `qdrant` *(vectors)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses
- **Overview Dashboards** — Stats & monitoring for RAG and Agentic AI
- **RAG Data Pipeline** — Ingest documents & search semantically

## Job Description

The **RAG** (Retrieval-Augmented Generation) is the data pipeline hub of UnifAI. It manages the entire document lifecycle — uploading, validating, converting, chunking, embedding, indexing, and searching — across multiple data source types (documents and Slack channels).

#### Key Features

- **Multi-source Ingestion**: Document uploads (PDF, DOCX, HTML, etc.) and Slack channel messages, each with dedicated pipeline handlers.
- **Async Pipeline Execution**: Heavy work (conversion, embedding, indexing) dispatched to Celery workers via RabbitMQ, keeping the API responsive.
- **Vector Semantic Search**: Embeddings stored in Qdrant; `query.match` endpoint used by both UI and MAS agents for retrieval.
- **Source-Type Plugin Model**: Each data source type (document, slack) has its own connector, chunker, validator, processor, and pipeline handler — all wired through a `RegistrationFactory`.
- **Local / Remote Adapter Switching**: Docling (document conversion) and embedding generation can run locally (in-process) or remotely (HTTP), controlled by feature flags.
- **Pipeline Monitoring**: Full metrics, error tracking, and log collection for every pipeline run.

#### Who Calls It

- **UI** — via `/api1` for all RAG dashboard operations (upload, embed, search, data source management)
- **Multi Agent System (MAS)** — via `RagClient` for search queries (`query.match`) during agent execution
- **Platform Backend** — via `ActionDispatcher` for config-triggered side-effects (e.g., Slack channel cleanup)
- **Slack** — via Events API webhook at `POST /api/slack/events` for real-time channel updates

#### Ingestion Pipeline Flow

When a document is uploaded or a Slack channel is added:

- **1. Registration** — validate source, check for duplicates, create metadata, build pipeline config
- **2. Dispatch** — `PipelineTaskDispatcher` enqueues a Celery task to the appropriate queue (`document_queue` or `slack_queue`)
- **3. Collection** — pipeline handler collects raw content (file bytes or Slack messages via API)
- **4. Processing** — convert to text (Docling for documents, message formatting for Slack)
- **5. Chunking** — split into overlapping chunks using source-specific strategies (PDF vs Slack thread chunkers)
- **6. Embedding** — generate vector embeddings (local sentence-transformers or remote OpenAI-compatible API)
- **7. Indexing** — upsert vectors + metadata into Qdrant collection (`document_data` or `slack_data`)
- **8. Status Update** — persist pipeline status, metrics, and any errors to MongoDB

#### Domain Concepts

- **Data Source** — a registered content origin (a document file or Slack channel) with metadata and pipeline status.
- **Pipeline** — a tracked execution of the ingestion flow for one data source, with status (PENDING → PROCESSING → COMPLETED/FAILED) and metrics.
- **Vector Collection** — Qdrant collections per source type: `document_data`, `slack_data`.
- **Registration** — the validation + metadata creation step before pipeline dispatch. Source-type specific via `RegistrationFactory`.
- **Terms Approval** — user-level approval tracking for data usage terms.

#### 14 Domain Services

- `DataSourceService` — CRUD + delete with vector cleanup
- `DocumentService` — document-specific operations
- `FileValidationService` — pre-upload validation (type, size, duplicates)
- `RetrievalService` — vector search (query.match)
- `PipelineService` — pipeline CRUD and status tracking
- `PipelineDispatchService` — registration + Celery dispatch orchestration
- `PipelineExecutor` — full pipeline lifecycle (collect → embed → store)
- `RegistrationService` — source registration flows
- `MonitoringService` — pipeline log/metrics orchestration
- `VectorStatsService` — chunk count aggregation
- `SlackEventService` — Slack event handler registry
- `SlackEventDispatchService` — webhook → Celery dispatch
- `SlackStatsService` — Slack aggregation stats
- `ServicesHealthService` — external service readiness checks

## Endpoints (27)

### Documents

| Method | Path | Summary |
|--------|------|--------|
| POST | `/docs/upload` | multipart file upload |
| POST | `/docs/validate` | pre-upload validation |
| GET | `/docs/supported-extensions` | allowed file types |
| GET | `/docs/available.docs.get` | list documents |
| GET | `/docs/available.tags.get` | document tags |
| GET | `/docs/query.match` | semantic search |

### Slack

| Method | Path | Summary |
|--------|------|--------|
| PUT | `/slack/fetch.available.slack.channels` | refresh from Slack API |
| GET | `/slack/available.slack.channels.get` | cached channel list |
| GET | `/slack/slack.channel.chunks` | chunk counts per channel |
| GET | `/slack/user.info.get` | Slack user info |
| GET | `/slack/query.match` | Slack semantic search |
| GET | `/slack/stats` | Slack aggregation stats |
| POST | `/slack/events` | Slack Events API webhook |

### Data Sources

| Method | Path | Summary |
|--------|------|--------|
| GET | `/data_sources/data.sources.get` | list all sources (paginated) |
| GET | `/data_sources/data.source.details.get` | single source detail |
| PUT | `/data_sources/data.source.update` | update metadata |
| DEL | `/data_sources/data.source.delete` | delete + vector cleanup |

### Pipelines & Vector

| Method | Path | Summary |
|--------|------|--------|
| PUT | `/pipelines/embed` | trigger embedding pipeline |
| GET | `/vector/chunks.counts` | chunk count per source |

### Terms Approval

| Method | Path | Summary |
|--------|------|--------|
| GET | `/terms_approval/user.approval.status.get` |  |
| POST | `/terms_approval/user.approval.record.post` |  |

### Settings & Health

| Method | Path | Summary |
|--------|------|--------|
| GET | `/settings/get.umami.settings` | analytics config |
| GET | `/health/` | liveness |
| GET | `/health/version` |  |
| GET | `/health/service.readiness.get` | external dep check |

### Celery Tasks (via RabbitMQ)

| Method | Path | Summary |
|--------|------|--------|
| TASK | `execute_pipeline_task` | full ingestion pipeline (document_queue / slack_queue) |
| TASK | `process_slack_events_task` | Slack event handling (slack_events_queue, 3 retries) |

## Port Abstractions (21)

| Port | Role | Adapter |
|------|------|--------|
| `VectorRepository` | store, search, delete embeddings | Qdrant |
| `PipelineRepository` | pipeline CRUD, stats, status | MongoDB |
| `DataSourceRepository` | source CRUD, pagination, distinct values | MongoDB |
| `MonitoringRepository` | metrics, errors, logs | MongoDB |
| `TermsApprovalRepository` | user approval tracking | MongoDB |
| `SlackChannelRepository` | channel CRUD, membership | MongoDB |
| `EmbeddingPort` | encode_texts, test_connection | local or remote |
| `EmbeddingGenerator` | generate_embeddings, generate_query_embedding | — |
| `ContentChunker` | chunk_content, estimate_token_count | — |
| `SourcePipelinePort` | collect, process, chunk_and_embed, cleanup | — |
| `PipelineTaskDispatcher` | dispatch, dispatch_batch | Celery |
| `RegistrationPort` | validate + register source | — |
| `SlackEventDispatcher` | dispatch events to Celery | — |
| `SlackEventHandler` | handle individual event types | — |
| `DocumentConverterPort` | convert_file, convert_url | Docling |
| `DataConnector` | test_connection per source type | — |
| `DataProcessor` | process, clean_content | — |
| `DataSourceValidator` | validate source config | — |
| `HealthCheckable` | service readiness protocol | — |
| `BotInstallationCheckerPort` | Slack bot installation check | — |
| `DuplicateCheckerPort` | document duplicate detection | — |

## File Path Patterns

| Category | Path |
|----------|------|
| Endpoints | `rag/infrastructure/http/*.py` |
| Ports | `rag/core/**/port*.py`, `rag/core/**/repository.py`, `rag/core/**/dispatcher.py`, `rag/core/**/base.py`, `rag/core/**/embedder.py`, `rag/core/**/chunker.py`, `rag/core/**/document_converter.py` |
| Composition Root | `rag/bootstrap/app_container.py` |
| Flask Factory | `rag/bootstrap/flask_app.py` |
| App Config | `rag/config/app_config.py` |
| Mongo Adapters | `rag/infrastructure/mongo/**/*.py` |
| Celery Workers | `rag/infrastructure/celery/workers/*.py` |

## Architecture

#### Design Pattern: Hexagonal Architecture

RAG uses **ports and adapters**. Domain logic in `core/` (~104 Python files) defines ports (ABCs). `infrastructure/` (~59 files) provides adapters. `bootstrap/app_container.py` (~640 lines) wires ~40 singletons via `@lru_cache`.

#### Directory Layout

- **`core/`** — 13 bounded contexts: pipeline, data_sources (document + slack), vector/retrieval, monitoring, registration, health, validation, user/terms. ~104 Python files.
- **`infrastructure/`** — Flask HTTP (8 blueprints), Celery workers, MongoDB repos, Qdrant, Slack API, Docling, Embedding adapters. ~59 files.
- **`bootstrap/`** — `app_container.py` (composition root), `factories.py` (local vs remote adapter switching), `flask_app.py`.
- **`config/`** — `AppConfig(SharedConfig)` with ~25 settings.

#### All 21 Port Abstractions

**Repository Ports (7)**

`VectorRepository` — store, search, delete embeddings (→ Qdrant)

`PipelineRepository` — pipeline CRUD, stats, status (→ MongoDB)

`DataSourceRepository` — source CRUD, pagination, distinct values (→ MongoDB)

`MonitoringRepository` — metrics, errors, logs (→ MongoDB)

`TermsApprovalRepository` — user approval tracking (→ MongoDB)

`SlackChannelRepository` — channel CRUD, membership (→ MongoDB)

`EmbeddingPort` — encode_texts, test_connection (→ local or remote)

**Service / Pipeline Ports (8)**

`EmbeddingGenerator` — generate_embeddings, generate_query_embedding

`ContentChunker` — chunk_content, estimate_token_count

`SourcePipelinePort` — collect, process, chunk_and_embed, cleanup

`PipelineTaskDispatcher` — dispatch, dispatch_batch (→ Celery)

`RegistrationPort` — validate + register source

`SlackEventDispatcher` — dispatch events to Celery

`SlackEventHandler` — handle individual event types

`DocumentConverterPort` — convert_file, convert_url (→ Docling)

**Connector / Validation Ports (6)**

`DataConnector` — test_connection per source type

`DataProcessor` — process, clean_content

`DataSourceValidator` — validate source config

`HealthCheckable` — service readiness protocol

`BotInstallationCheckerPort` — Slack bot installation check

`DuplicateCheckerPort` — document duplicate detection

#### Port → Adapter Wiring

| Port | Adapter | Tech |
|---|---|---|
| `VectorRepository` | QdrantVectorRepository | Qdrant |
| `PipelineRepository` | MongoPipelineRepository | MongoDB |
| `DataSourceRepository` | MongoDataSourceRepository | MongoDB |
| `MonitoringRepository` | MongoMonitoringRepository | MongoDB |
| `SlackChannelRepository` | MongoSlackChannelRepository | MongoDB |
| `TermsApprovalRepository` | MongoTermsApprovalRepository | MongoDB |
| `EmbeddingPort` | Local / RemoteEmbeddingAdapter | sentence-transformers / HTTP |
| `DocumentConverterPort` | Local / RemoteDoclingAdapter | Docling / HTTP |
| `PipelineTaskDispatcher` | CeleryPipelineDispatcher | RabbitMQ |
| `SlackEventDispatcher` | CelerySlackEventDispatcher | RabbitMQ |
| `DataConnector` | DocumentConnector / SlackConnector | Filesystem / Slack API |
| `ContentChunker` | PDFChunkerStrategy / SlackChunkerStrategy | LangChain splitters |

#### MongoDB (3 databases, 7+ collections)

| Database | Collection | Used By |
|---|---|---|
| pipeline_monitoring | pipelines | MongoPipelineRepository |
| pipeline_monitoring | metrics | MongoMonitoringRepository |
| pipeline_monitoring | errors | MongoMonitoringRepository |
| pipeline_monitoring | logs | MongoMonitoringRepository |
| data_sources | sources | MongoDataSourceRepository |
| data_sources | slack_channels | MongoSlackChannelRepository |
| users | terms_user_approval | MongoTermsApprovalRepository |

#### Qdrant Collections (vector store)

| Collection | Source Type |
|---|---|
| `document_data` | DOCUMENT |
| `slack_data` | SLACK |

#### Source-Type Plugin Architecture

Each source type (document, slack) provides its own: `Connector`, `Processor`, `ChunkerStrategy`, `Validator(s)`, `PipelineHandler`, `Registration`, and `ConfigManager`. The `RegistrationFactory` and `get_pipeline_handler()` select the correct set based on source type.

#### Key Configuration (AppConfig)

| Setting | Default | Purpose |
|---|---|---|
| `port` | 13456 | Flask server port |
| `use_remote_docling` | false | Local vs remote document conversion |
| `use_remote_embedding` | false | Local vs remote embedding generation |
| `qdrant_ip / qdrant_port` | localhost:6333 | Qdrant connection |
| `docling_service_url` | (empty) | Remote Docling endpoint |
| `embedding_service_url` | (empty) | Remote embedding endpoint |
| `embedding_dim` | 384 | Vector dimension |
| `default_slack_bot_token` | (empty) | Slack API token |

## Class Architecture

RAG follows **hexagonal architecture**: domain logic in `core/` defines ports (ABCs), `infrastructure/` provides adapters, and `bootstrap/` wires them together via `app_container` (lru_cache singletons).

### Key Extension Points

These are the base classes and ABCs that new code should extend or implement:

| Class | File | Layer | Implementations / Subclasses |
|-------|------|-------|------------------------------|
| `SourcePipelinePort (ABC)` | `core/pipeline/domain/port.py` | Core — Pipeline | `DocumentPipelineHandler`, `SlackPipelineHandler` |
| `PipelineTaskDispatcher (ABC)` | `core/pipeline/domain/dispatcher.py` | Core — Pipeline | `CeleryPipelineDispatcher` |
| `VectorRepository (ABC)` | `core/vector/domain/repository.py` | Core — Vector & Retrieval | `QdrantVectorRepository`, `PipelineExecutor`, `DataSourceService`, `RetrievalService`, `VectorStatsService` |
| `EmbeddingGenerator (ABC)` | `core/vector/domain/embedder.py` | Core — Vector & Retrieval | `DefaultEmbeddingGenerator`, `DocumentPipelineHandler`, `SlackPipelineHandler`, `RetrievalService` |
| `ContentChunker (ABC)` | `core/vector/domain/chunker.py` | Core — Vector & Retrieval | `PDFChunkerStrategy`, `SlackChunkerStrategy` |

### Bootstrap & Factories

| Class | File | Role |
|-------|------|------|
| `DocumentConverterFactory` | `bootstrap/factories.py` | Builds local or remote Docling adapter based on config |
| `DocumentConnectorFactory` | `bootstrap/factories.py` | Builds DocumentConnector with chosen converter |
| `EmbeddingPortFactory` | `bootstrap/factories.py` | Builds local or remote embedding adapter |
| `EmbeddingGeneratorFactory` | `bootstrap/factories.py` | Wraps EmbeddingPort in DefaultEmbeddingGenerator |
| `VectorRepositoryFactory` | `bootstrap/factories.py` | Builds QdrantVectorRepository from config |

- `DocumentConverterFactory` calls: `LocalDoclingAdapter`, `RemoteDoclingAdapter`, `global_utils:DoclingClient`, `global_utils:DoclingService`
- `DocumentConverterFactory` called by: `DocumentConnectorFactory`
- `DocumentConnectorFactory` calls: `DocumentConverterFactory`, `DocumentConnector`, `DocConfigManager`
- `DocumentConnectorFactory` called by: `AppContainer`
- `EmbeddingPortFactory` calls: `LocalEmbeddingAdapter`, `RemoteEmbeddingAdapter`, `global_utils:EmbeddingClient`, `global_utils:EmbeddingService`
- `EmbeddingPortFactory` called by: `EmbeddingGeneratorFactory`

### Core — Pipeline

| Class | File | Role |
|-------|------|------|
| `PipelineExecutor` | `core/pipeline/executor.py` | Orchestrates pipeline stages: collect → process → chunk → embed → store |
| `PipelineService` | `core/pipeline/service.py` | CRUD and status tracking for pipeline records |
| `PipelineDispatchService` | `core/pipeline/dispatch_service.py` | Registers sources then dispatches batch tasks |
| `SourcePipelinePort (ABC)` | `core/pipeline/domain/port.py` | Port: collect/process/chunk_embed per source type |
| `PipelineTaskDispatcher (ABC)` | `core/pipeline/domain/dispatcher.py` | Port to enqueue async pipeline work |
| `PipelineRecord` | `core/pipeline/domain/model.py` | Aggregate root for pipeline tracking (status, stats) |

- `PipelineExecutor` calls: `PipelineService`, `MonitoringService`, `DataSourceService`, `VectorRepository`, `SourcePipelinePort`
- `PipelineExecutor` called by: `Celery: execute_pipeline_task`
- `PipelineRecord` called by: `PipelineRepository`, `PipelineService`, `MonitoringService`

### Core — Data Sources & Registration

| Class | File | Role |
|-------|------|------|
| `DataSourceService` | `core/data_sources/service.py` | CRUD, enrichment with pipeline stats, delete (vectors + mongo) |
| `RegistrationService` | `core/registration/service.py` | Loops items through factory-created registrars |
| `RegistrationFactory` | `core/registration/factory.py` | Chooses DocumentRegistration vs SlackRegistration |
| `DocumentRegistration` | `core/data_sources/types/document/registration.py` | Validates and registers document sources |
| `SlackRegistration` | `core/data_sources/types/slack/registration.py` | Validates and registers Slack channel sources |
| `DocumentService` | `core/data_sources/types/document/document_service.py` | DONE-only doc listing for UI |
| `FileValidationService` | `core/data_sources/types/document/file_validation_service.py` | Pre-upload validation (extension, size, duplicates) |

- `DataSourceService` calls: `DataSourceRepository`, `PipelineRepository`, `VectorRepository`
- `DataSourceService` called by: `PipelineExecutor`, `DocumentService`, `data_sources_bp`
- `RegistrationFactory` calls: `DocumentRegistration`, `SlackRegistration`, `DataSourceRepository`
- `RegistrationFactory` called by: `RegistrationService`
- `DocumentRegistration` calls: `BaseRegistration`, `Validator`, `DocValidators`
- `DocumentRegistration` called by: `RegistrationFactory`
- `SlackRegistration` calls: `BaseRegistration`, `Validator`, `SlackValidators`
- `SlackRegistration` called by: `RegistrationFactory`

### Core — Vector & Retrieval

| Class | File | Role |
|-------|------|------|
| `VectorRepository (ABC)` | `core/vector/domain/repository.py` | Port: init/store/search/count/delete vectors |
| `EmbeddingGenerator (ABC)` | `core/vector/domain/embedder.py` | Port: batch embed chunks and queries |
| `RetrievalService` | `core/retrieval/service.py` | Embed query + vector search with source filters |
| `VectorStatsService` | `core/vector/stats_service.py` | Qdrant chunk counts per collection |
| `ContentChunker (ABC)` | `core/vector/domain/chunker.py` | Chunking strategy contract |

- `VectorRepository (ABC)` called by: `QdrantVectorRepository`, `PipelineExecutor`, `DataSourceService`, `RetrievalService`, `VectorStatsService`
- `EmbeddingGenerator (ABC)` called by: `DefaultEmbeddingGenerator`, `DocumentPipelineHandler`, `SlackPipelineHandler`, `RetrievalService`
- `RetrievalService` calls: `EmbeddingGenerator`, `VectorRepository`, `SourceFilterResolver`
- `RetrievalService` called by: `docs_bp`, `slack_bp`

### Core — Monitoring & Health

| Class | File | Role |
|-------|------|------|
| `MonitoringService` | `core/monitoring/service.py` | Metrics, errors, logs capture via logging handler |
| `ServicesHealthService` | `core/health/service.py` | Registry of HealthCheckable ports; check_all() |
| `LogParser` | `core/monitoring/parsing/base.py` | Extracts chunk/embedding counts from log lines |

- `MonitoringService` calls: `MonitoringRepository`, `PipelineRepository`, `LogParser`
- `MonitoringService` called by: `PipelineExecutor`

### Core — Pipeline Handlers

| Class | File | Role |
|-------|------|------|
| `DocumentPipelineHandler` | `core/data_sources/types/document/pipeline_handler.py` | SourcePipelinePort for documents: convert → chunk → embed |
| `SlackPipelineHandler` | `core/data_sources/types/slack/pipeline_handler.py` | SourcePipelinePort for Slack: fetch → process → chunk → embed |

- `DocumentPipelineHandler` calls: `DocumentConnector`, `DocumentProcessor`, `PDFChunkerStrategy`, `EmbeddingGenerator`
- `DocumentPipelineHandler` called by: `PipelineExecutor`
- `SlackPipelineHandler` calls: `SlackConnector`, `SlackProcessor`, `SlackChunkerStrategy`, `EmbeddingGenerator`
- `SlackPipelineHandler` called by: `PipelineExecutor`

### Infrastructure — MongoDB

| Class | File | Role |
|-------|------|------|
| `MongoPipelineRepository` | `infrastructure/mongo/pipeline_repository.py` | PipelineRepository adapter for pipelines collection |
| `MongoDataSourceRepository` | `infrastructure/mongo/data_source_repository.py` | DataSourceRepository adapter with paginated queries |
| `MongoMonitoringRepository` | `infrastructure/mongo/monitoring_repository.py` | MonitoringRepository adapter for metrics/errors/logs |
| `MongoSlackChannelRepository` | `infrastructure/mongo/data_sources/slack_channel_repository.py` | SlackChannelRepository adapter |
| `PaginatedQueryBuilder` | `infrastructure/mongo/pagination_builder.py` | Fluent Mongo aggregation for paged docs |

### Infrastructure — Qdrant & Embedding

| Class | File | Role |
|-------|------|------|
| `QdrantVectorRepository` | `infrastructure/qdrant/qdrant_vector_repository.py` | VectorRepository: collection lifecycle, upsert, search, filter delete |
| `DefaultEmbeddingGenerator` | `infrastructure/embedding/embedding_generator.py` | Batched EmbeddingGenerator over EmbeddingPort |
| `LocalEmbeddingAdapter` | `infrastructure/embedding/embedders/local_embedding_adapter.py` | EmbeddingPort using SentenceTransformer locally |
| `RemoteEmbeddingAdapter` | `infrastructure/embedding/embedders/remote_embedding_adapter.py` | EmbeddingPort calling remote HTTP /v1/embeddings |

### Infrastructure — Celery & Sources

| Class | File | Role |
|-------|------|------|
| `CeleryPipelineDispatcher` | `infrastructure/celery/pipeline_dispatcher.py` | PipelineTaskDispatcher via Celery send_task |
| `DocumentConnector` | `infrastructure/sources/document/connector.py` | File → ProcessedDocument via converter |
| `SlackConnector` | `infrastructure/sources/slack/connector.py` | Slack Web API: history, caching, threads |
| `PDFChunkerStrategy` | `infrastructure/sources/document/chunker.py` | ContentChunker using tiktoken + RecursiveCharacterTextSplitter |
| `SlackChunkerStrategy` | `infrastructure/sources/slack/chunker.py` | ContentChunker for Slack messages/threads |
| `LocalDoclingAdapter` | `infrastructure/sources/document/converters/local_docling_adapter.py` | DocumentConverterPort using local docling library |
| `RemoteDoclingAdapter` | `infrastructure/sources/document/converters/remote_docling_adapter.py` | DocumentConverterPort calling remote Docling service |

- `SlackConnector` calls: `SlackConfigManager`, `SlackChannelRepository`, `SlackThreadRetriever`
- `SlackConnector` called by: `SlackPipelineHandler`, `slack_bp`

### Core — Slack Events

| Class | File | Role |
|-------|------|------|
| `SlackEventService` | `core/data_sources/types/slack/event_service.py` | Registry of SlackEventHandler implementations; routes by event type |
| `SlackEventDispatchService` | `core/data_sources/types/slack/event_dispatch_service.py` | Validates webhook → dispatches to Celery via SlackEventDispatcher |
| `SlackStatsService` | `core/data_sources/types/slack/slack_stats_service.py` | Aggregation stats: channel chunk counts, user info lookups |
| `CelerySlackEventDispatcher` | `infrastructure/celery/slack_event_dispatcher.py` | SlackEventDispatcher adapter: enqueues to slack_events_queue |

### Core — Terms & Settings

| Class | File | Role |
|-------|------|------|
| `TermsApprovalService` | `core/terms_approval/service.py` | User-level data usage approval tracking |
| `MongoTermsApprovalRepository` | `infrastructure/mongo/terms_approval_repository.py` | TermsApprovalRepository adapter for users.terms_user_approval |

### Infrastructure — Flask HTTP (8 Blueprints)

| Class | File | Role |
|-------|------|------|
| `docs_bp` | `infrastructure/flask/docs_routes.py` | Upload, validate, list, search, tags, supported-extensions |
| `slack_bp` | `infrastructure/flask/slack_routes.py` | Channel fetch, list, chunks, user info, search, stats, events webhook |
| `data_sources_bp` | `infrastructure/flask/data_sources_routes.py` | List, detail, update, delete with vector cleanup |
| `pipelines_bp` | `infrastructure/flask/pipelines_routes.py` | Trigger embedding pipeline (dispatch) |
| `vector_bp` | `infrastructure/flask/vector_routes.py` | Chunk counts per source type |
| `terms_approval_bp` | `infrastructure/flask/terms_approval_routes.py` | Approval status check and record |
| `settings_bp` | `infrastructure/flask/settings_routes.py` | Umami analytics settings |
| `health_bp` | `infrastructure/flask/health_routes.py` | Liveness, version, service readiness |

- `docs_bp` calls: `DocumentService`, `FileValidationService`, `RetrievalService`, `PipelineDispatchService`
- `docs_bp` called by: `Flask: router`
- `slack_bp` calls: `SlackConnector`, `SlackStatsService`, `SlackEventDispatchService`, `RetrievalService`
- `slack_bp` called by: `Flask: router`

---

*Source: `js/data/services/rag.js`* | *Classes: `js/data-classes/rag.js`*
