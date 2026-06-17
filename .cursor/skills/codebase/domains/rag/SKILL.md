---
name: rag-knowledge
description: >-
  RAG domain knowledge — architecture, component routing, rules, and reference tables.
  Use when working on any file under rag/.
paths: rag/**
---

# RAG Knowledge System

Document ingestion and retrieval engine: data sources → processing pipeline → vector storage → semantic retrieval.

## System Graph

```
         ┌──────────┐
         │ BOOTSTRAP│ wires ~40 singletons via @lru_cache
         └────┬─────┘
              │
    ┌─────────┼──────────────┐
    ▼         ▼              ▼
┌────────┐ ┌────────────┐ ┌──────────────┐
│PIPELINE│→│DATA-SOURCES│→│VECTOR-RETRIEVAL│   CORE (rag/core/ ~104 files)
└───┬────┘ └─────┬──────┘ └──────┬───────┘
    │             │               │
    ▼             ▼               ▼
┌──────────────────────────────────────┐
│          INFRASTRUCTURE              │   OUTER RING (~59 files)
│  flask (8 bps), mongo (7 colls),    │
│  qdrant (2 colls), celery (3 queues)│
│  source connectors, embeddings      │
└──────────────────────────────────────┘
```

## File → Component Routing

| Path prefix | Component | Dev-guide section |
|-------------|-----------|-------------------|
| `core/pipeline/` | Pipeline | `rag.md → core_pipeline` |
| `core/data_sources/`, `core/connector/`, `core/registration/` | Data Sources | `rag.md → core_data_sources_registration` |
| `core/vector/`, `core/retrieval/` | Vector Retrieval | `rag.md → core_vector_retrieval` |
| `core/monitoring/`, `core/health/` | Infrastructure | `rag.md → core_monitoring_health` |
| `infrastructure/` | Infrastructure | `rag.md → architecture` |
| `bootstrap/`, `config/` | Bootstrap | `rag.md → bootstrap_factories` |

## Component Deep-Dives

For detailed component architecture and cross-component contracts:

| Component | Reference |
|-----------|-----------|
| Pipeline | `references/pipeline.md` — execution, dispatch, status tracking, Celery integration |
| Data Sources | `references/data-sources.md` — source types, plugin model, connectors, registration |
| Vector Retrieval | `references/vector-retrieval.md` — embeddings, chunking, Qdrant, semantic search |
| Infrastructure | `references/infrastructure.md` — Flask, Mongo, Qdrant, Celery, port-adapter wiring |
| Bootstrap | `references/bootstrap.md` — composition root, factories, config, local/remote switching |

## Task Router

| Working on... | Load |
|---------------|------|
| Pipeline execution, dispatch, Celery tasks | `references/pipeline.md` |
| Source types (document, Slack), connectors, registration | `references/data-sources.md` |
| Embeddings, chunking, Qdrant, semantic search | `references/vector-retrieval.md` |
| Flask endpoints, Mongo repos, Qdrant client, Celery | `references/infrastructure.md` |
| Wiring, config, factories, local/remote switching | `references/bootstrap.md` |
| Crossing component boundaries | Both relevant `references/` files |

---

## RAG Architectural Rules

### 1. Pipeline Execution Flow

All document processing follows the strict pipeline pattern:

```
Registration → Dispatch (Celery) → Collect → Process → Chunk → Embed → Index → Status Update
```

Each stage is a discrete unit communicating via Pydantic models.
`PipelineRecord` tracks status: `PENDING → PROCESSING → COMPLETED | FAILED`.
Pipeline state is persisted for crash-recovery.

### 2. Source-Type Plugin Architecture

Each source type (document, Slack) provides its own set:
`Connector`, `Processor`, `ChunkerStrategy`, `Validator(s)`, `PipelineHandler`, `Registration`, `ConfigManager`.

`RegistrationFactory` and `get_pipeline_handler()` select the correct set based on source type.
No `if/elif` chains for type resolution — factory pattern only.

### 3. Vector Storage Abstraction

All vector operations go through `VectorRepository` (ABC in `core/vector/domain/repository.py`).
The `QdrantVectorRepository` adapter implements this port.
Domain code never imports Qdrant client directly.

Two collections: `document_data`, `slack_data`.

### 4. Celery Task Boundaries

Celery tasks in `infrastructure/celery/workers/` are thin dispatchers:
1. Resolve dependencies from app container
2. Call `PipelineExecutor` or domain service
3. Return result

Business logic never lives inside a Celery task function.
Three queues: `document_queue`, `slack_queue`, `slack_events_queue`.

### 5. Local / Remote Adapter Switching

Docling (document conversion) and embedding generation can run:
- **Locally** (in-process: `LocalDoclingAdapter`, `LocalEmbeddingAdapter`)
- **Remotely** (HTTP: `RemoteDoclingAdapter`, `RemoteEmbeddingAdapter`)

Controlled by config flags: `use_remote_docling`, `use_remote_embedding`.
Factories in `bootstrap/factories.py` select the adapter at startup.

### 6. Port-per-Adapter Enforcement

21 port abstractions in RAG core. Every adapter implements exactly one port.
Key port categories:
- **Repository ports** (7): VectorRepository, PipelineRepository, DataSourceRepository, etc.
- **Service/pipeline ports** (8): EmbeddingGenerator, ContentChunker, SourcePipelinePort, etc.
- **Connector/validation ports** (6): DataConnector, DataProcessor, HealthCheckable, etc.

### 7. Composition Root — `@lru_cache` Singletons

`app_container.py` wires ~40 singletons via `@lru_cache` property methods.
All dependency injection flows through this container.
Services receive dependencies as constructor parameters — no service locator.

### Established Patterns — RAG Service

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `@lru_cache` singleton container with parameterized caches | `bootstrap/app_container.py` (~640 lines, ~40 singletons) | Composition root — explicit function-call graphs, not string-keyed lookup; `clear_all_caches()` for tests |
| Celery tasks importing directly from `bootstrap.app_container` | `infrastructure/celery/workers/pipeline_tasks.py`, `slack_event_tasks.py` | Tasks are driving adapters; 3-line delegate pattern (resolve → select handler → execute) |
| Factory classes with `if config.use_remote_*` branching + lazy imports | `bootstrap/factories.py`, adapter `__init__.py` with PEP 562 `__getattr__` | Encapsulated local/remote switching; prevents heavy deps (torch, docling) from loading in remote mode |
| LangChain (`langchain_text_splitters`) in chunker implementations | `infrastructure/sources/document/chunker.py`, `infrastructure/sources/slack/chunker.py` | Chunkers are infrastructure adapters implementing `ContentChunker` port; core has ABC only |
| `AppConfig.get_instance()` ambient singleton | Called from `bootstrap/`, `infrastructure/http/`, `infrastructure/celery/app.py` | Pydantic BaseSettings singleton — monorepo convention; bootstrap reads once, never from core |
| `get_pipeline_handler()` registry dict in `app_container` | Maps `"SLACK"` / `"DOCUMENT"` → cached factory functions | Handler routing by source type; dictionary acts as a factory, not a service locator |
| `SourceFilterResolver` injected without core port | `core/retrieval/service.py` accepts concrete `SourceFilterResolver` | Query helper for Qdrant filter composition; accepted typing shortcut — runtime injection is still via container |
| Pipeline handlers in `core/` importing concrete infrastructure types in type hints | `DocumentPipelineHandler` → `DocumentConnector`, `PDFChunkerStrategy` | Constructor injection is correct; the import-direction blur is typing only, not runtime coupling |

---

## Endpoint Groups

| Group | Count | Prefix | Key operations |
|-------|-------|--------|----------------|
| Documents | 6 | `/docs/` | upload, validate, query.match, list, tags |
| Slack | 7 | `/slack/` | channels, search, events, stats, webhook |
| Data Sources | 4 | `/data_sources/` | list, detail, update, delete |
| Pipelines/Vector | 2 | `/pipelines/`, `/vector/` | embed trigger, chunk counts |
| Terms Approval | 2 | `/terms_approval/` | approval status, record |
| Health/Settings | 5 | `/health/`, `/settings/` | liveness, readiness, version, analytics |
| Celery Tasks | 2 | (RabbitMQ) | execute_pipeline, process_slack_events |

## Port → Adapter Wiring

| Port | Adapter | Tech |
|------|---------|------|
| `VectorRepository` | `QdrantVectorRepository` | Qdrant |
| `PipelineRepository` | `MongoPipelineRepository` | MongoDB |
| `DataSourceRepository` | `MongoDataSourceRepository` | MongoDB |
| `MonitoringRepository` | `MongoMonitoringRepository` | MongoDB |
| `SlackChannelRepository` | `MongoSlackChannelRepository` | MongoDB |
| `TermsApprovalRepository` | `MongoTermsApprovalRepository` | MongoDB |
| `EmbeddingPort` | `LocalEmbeddingAdapter` / `RemoteEmbeddingAdapter` | sentence-transformers / HTTP |
| `DocumentConverterPort` | `LocalDoclingAdapter` / `RemoteDoclingAdapter` | Docling / HTTP |
| `PipelineTaskDispatcher` | `CeleryPipelineDispatcher` | RabbitMQ |
| `SlackEventDispatcher` | `CelerySlackEventDispatcher` | RabbitMQ |
| `DataConnector` | `DocumentConnector` / `SlackConnector` | Filesystem / Slack API |
| `ContentChunker` | `PDFChunkerStrategy` / `SlackChunkerStrategy` | LangChain splitters |

## MongoDB & Qdrant Collections

| Store | Database | Collection | Adapter / Source Type |
|-------|----------|------------|----------------------|
| MongoDB | `pipeline_monitoring` | `pipelines` | `MongoPipelineRepository` |
| MongoDB | `pipeline_monitoring` | `metrics`, `errors`, `logs` | `MongoMonitoringRepository` |
| MongoDB | `data_sources` | `sources` | `MongoDataSourceRepository` |
| MongoDB | `data_sources` | `slack_channels` | `MongoSlackChannelRepository` |
| MongoDB | `users` | `terms_user_approval` | `MongoTermsApprovalRepository` |
| Qdrant | — | `document_data` | DOCUMENT source type |
| Qdrant | — | `slack_data` | SLACK source type |

## Factual Reference (optional)

For full endpoint signatures, class architecture, port catalogs, and call graphs beyond the tables above:
`.cursor/unifai-dev-guide/docs/services/rag.md`
