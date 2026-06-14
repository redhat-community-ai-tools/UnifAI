---
name: rag-service
scope: RAG — document ingestion, processing, and retrieval-augmented generation
parent: ../SKILL.md
children:
  - pipeline/_index.md
  - data-sources/_index.md
  - vector-retrieval/_index.md
  - infrastructure/_index.md
  - bootstrap/_index.md
when_to_load: Any work touching rag/ directory
---

# RAG Service

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

| Path prefix | Load | Dev-guide section |
|-------------|------|-------------------|
| `core/pipeline/` | `pipeline/` | `rag.md → core_pipeline` |
| `core/data_sources/`, `core/connector/`, `core/registration/` | `data-sources/` | `rag.md → core_data_sources_registration` |
| `core/vector/`, `core/retrieval/` | `vector-retrieval/` | `rag.md → core_vector_retrieval` |
| `core/monitoring/`, `core/health/` | `infrastructure/` | `rag.md → core_monitoring_health` |
| `infrastructure/` | `infrastructure/` | `rag.md → architecture` |
| `bootstrap/`, `config/` | `bootstrap/` | `rag.md → bootstrap_factories` |

## Task Router

| Working on... | Load |
|---------------|------|
| Pipeline execution, dispatch, Celery tasks | `pipeline/_index.md` |
| Source types (document, Slack), connectors, registration | `data-sources/_index.md` |
| Embeddings, chunking, Qdrant, semantic search | `vector-retrieval/_index.md` |
| Flask endpoints, Mongo repos, Qdrant client, Celery | `infrastructure/_index.md` |
| Wiring, config, factories, local/remote switching | `bootstrap/_index.md` |
| Crossing component boundaries | Both `_index.md` + target's `relationships.md` |

## Landmarks

| Landmark | Location |
|----------|----------|
| Composition root | `rag/bootstrap/app_container.py` (~640 lines, ~40 singletons) |
| Flask factory | `rag/bootstrap/flask_app.py` |
| Factories | `rag/bootstrap/factories.py` (local/remote adapter switching) |
| App config | `rag/config/app_config.py` (extends SharedConfig, ~25 settings) |
| Shared config | `global_utils/src/global_utils/config/config.py` |
| API endpoints | `rag/infrastructure/http/*.py` (8 blueprints, 27 endpoints) |
| Blueprint registration | `rag/infrastructure/http/blueprints.py` |
| Mongo adapters | `rag/infrastructure/mongo/**/*.py` |
| Celery workers | `rag/infrastructure/celery/workers/*.py` |
| Port definitions | `rag/core/**/port*.py`, `repository.py`, `dispatcher.py`, `base.py` |

## 14 Domain Services

| Service | Role |
|---------|------|
| `DataSourceService` | CRUD + delete with vector cleanup |
| `DocumentService` | Document-specific operations |
| `FileValidationService` | Pre-upload validation (type, size, duplicates) |
| `RetrievalService` | Vector search (query.match) |
| `PipelineService` | Pipeline CRUD and status tracking |
| `PipelineDispatchService` | Registration + Celery dispatch |
| `PipelineExecutor` | Full pipeline lifecycle (collect → embed → store) |
| `RegistrationService` | Source registration flows |
| `MonitoringService` | Pipeline log/metrics orchestration |
| `VectorStatsService` | Chunk count aggregation |
| `SlackEventService` | Slack event handler registry |
| `SlackEventDispatchService` | Webhook → Celery dispatch |
| `SlackStatsService` | Slack aggregation stats |
| `ServicesHealthService` | External service readiness checks |

## Dev-Guide Facts

For class architecture, endpoint signatures, port catalogs, and MongoDB/Qdrant schemas:
- **Service doc:** `unifai-dev-guide/docs/services/rag.md`
- **Source map:** `unifai-dev-guide/source-map.yaml → rag`
- **Code → doc routing:** `unifai-dev-guide/guide-index.yaml` (maps `rag/**` globs to rag.md sections)

## Navigation

1. Identify component from routing table
2. Load `<component>/_index.md`
3. If crossing boundaries → load target's `relationships.md`
4. Before writing code → load `rules.md` + `../../architecture/standards.md`
