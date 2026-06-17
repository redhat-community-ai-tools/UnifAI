---
service: celery
type: WORKER
code_root: rag/  # same codebase as RAG
sections:
  connections: 27
  features: 34
  job_description: 38
  endpoints_4: 56
  architecture: 67
  class_architecture: 86
---

# RAG Celery Workers

> Async ingestion pipelines

| Field | Value |
|-------|-------|
| ID | `celery` |
| Type | WORKER |
| Tech Stack | Celery, RabbitMQ |
| Code Root | `rag/  # same codebase as RAG` |
| Shares Codebase With | rag |
| Subtitle | Celery • RabbitMQ broker • 3 queues |

## Connections

**Outgoing:**
- `celery` → `rabbitmq` *(consume)*
- `celery` → `mongodb` *(status)*
- `celery` → `qdrant` *(upsert)*

## Features

- **RAG Data Pipeline** — Ingest documents & search semantically

## Job Description

**Celery Workers** handle all the heavy, long-running work for RAG: converting documents, generating embeddings, and indexing vectors. They run as separate processes to keep the API responsive.

#### Pipeline Flow

- **1. Receive** — task arrives from RabbitMQ queue
- **2. Convert** — parse document (PDF, DOCX, etc.) into text via Docling
- **3. Chunk** — split text into overlapping chunks (LangChain splitters)
- **4. Embed** — generate vector embeddings (local or remote)
- **5. Index** — upsert vectors + metadata into Qdrant

#### Three Queues

- `document_queue` — document ingestion pipelines
- `slack_queue` — Slack channel ingestion pipelines
- `slack_events_queue` — real-time Slack event processing

## Endpoints (4)

### General

| Method | Path | Summary |
|--------|------|--------|
| TASK | `execute_pipeline_task` | runs full ingestion pipeline |
| TASK | `process_slack_events_task` | handles Slack events (3 retries) |
| POST | `Docling: /v1/convert/file, /v1/convert/source` |  |
| POST | `Embedding: /v1/embeddings (OpenAI-compatible)` |  |

## Architecture

#### Entry Point

`rag/entrypoint.sh` with `ROLE=celery` runs:

`celery -A infrastructure.celery.app worker -Q $CELERY_QUEUES`

#### Key Files

- `infrastructure/celery/app.py` — Celery app configuration
- `infrastructure/celery/workers/pipeline_tasks.py` — pipeline execution task
- `infrastructure/celery/workers/slack_event_tasks.py` — Slack event task
- `infrastructure/celery/pipeline_dispatcher.py` — routes tasks to queues

#### Local vs Remote

Worker pool type depends on config: `threads` pool when using remote Docling/embedding, `solo` pool for local processing.

## Class Architecture

Celery Workers run inside the RAG codebase (`rag/infrastructure/celery/`). They consume tasks from RabbitMQ and drive the `PipelineExecutor` with source-specific handlers.

### Worker Entry

| Class | File | Role |
|-------|------|------|
| `CeleryApp (global_utils)` | `global_utils/celery_app/init.py` | Celery application factory with RabbitMQ broker + Mongo backend |
| `execute_pipeline_task()` | `rag/infrastructure/celery/workers/pipeline_tasks.py` | Task entry point: builds context, selects handler, calls PipelineExecutor |
| `process_slack_events_task()` | `rag/infrastructure/celery/workers/slack_event_tasks.py` | Task: dispatches Slack webhook events to handlers |

- `execute_pipeline_task()` calls: `rag:PipelineExecutor`, `rag:DocumentPipelineHandler`, `rag:SlackPipelineHandler`
- `execute_pipeline_task()` called by: `Celery: from RabbitMQ`

### Pipeline Execution (from RAG core)

| Class | File | Role |
|-------|------|------|
| `PipelineExecutor` | `rag/core/pipeline/executor.py` | Drives pipeline stages: collect → process → chunk → embed → store |
| `DocumentPipelineHandler` | `rag/core/data_sources/types/document/pipeline_handler.py` | SourcePipelinePort: Docling → chunk → embed for documents |
| `SlackPipelineHandler` | `rag/core/data_sources/types/slack/pipeline_handler.py` | SourcePipelinePort: fetch Slack → process → chunk → embed |

- `PipelineExecutor` calls: `rag:SourcePipelinePort`, `rag:PipelineService`, `rag:MonitoringService`, `rag:VectorRepository`
- `PipelineExecutor` called by: `execute_pipeline_task()`
- `DocumentPipelineHandler` calls: `rag:DocumentConnector`, `rag:PDFChunkerStrategy`, `rag:EmbeddingGenerator`
- `DocumentPipelineHandler` called by: `PipelineExecutor`
- `SlackPipelineHandler` calls: `rag:SlackConnector`, `rag:SlackChunkerStrategy`, `rag:EmbeddingGenerator`
- `SlackPipelineHandler` called by: `PipelineExecutor`

### External Service Calls

| Class | File | Role |
|-------|------|------|
| `LocalDoclingAdapter / RemoteDoclingAdapter` | `rag/infrastructure/sources/document/converters/` | Document conversion (local library or remote HTTP) |
| `LocalEmbeddingAdapter / RemoteEmbeddingAdapter` | `rag/infrastructure/embedding/embedders/` | Embedding generation (local SentenceTransformer or remote HTTP) |
| `QdrantVectorRepository` | `rag/infrastructure/qdrant/qdrant_vector_repository.py` | Vector storage: upsert, search, delete in Qdrant |

---

*Source: `js/data/services/celery.js`* | *Classes: `js/data-classes/celery.js`*
