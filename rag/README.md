# RAG Module

> **Data Pipeline Hub** — Feature-sliced architecture implementation for document and Slack data ingestion with vector search capabilities.

## Overview

The RAG (Retrieval-Augmented Generation) module handles data ingestion pipelines for multiple source types, processing content into vector embeddings for semantic search. Built with a **Feature-Sliced Architecture** combining hexagonal principles with vertical organization for maximum cohesion and maintainability.

### Key Features

- 📄 **Document Processing** — PDF, Markdown ingestion with intelligent chunking
- 💬 **Slack Integration** — Channel and thread message indexing
- 🔍 **Vector Search** — Semantic similarity search via Qdrant
- ⚡ **Async Pipelines** — Celery-based background task execution
- 🔌 **Pluggable Adapters** — Easy to swap MongoDB, Qdrant, or add new sources

---

## Architecture

```
rag/
├── core/            # 🎯 Business logic + services (domain + use cases)
├── infrastructure/  # 🔌 Adapters (Mongo, Qdrant, Celery, HTTP, Sources)
├── bootstrap/       # ⚡ Dependency injection & app setup
├── config/          # ⚙️ Configuration management
├── shared/          # 🔧 Cross-cutting utilities (logging)
```

### Layer Responsibilities

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| **Core** | Business rules, domain models, ports, services | None (pure Python) |
| **Infrastructure** | External system adapters | Core + external libs |
| **Bootstrap** | Wiring, DI container, app factory | All layers |

### Dependency Flow

```
Infrastructure ───────▶ Core ◀──────── Bootstrap
   (Adapters)       (Domain + Services)    (Wiring)

         Adapters depend on Core abstractions,
              Core has no dependencies!
```

📖 **See [DIAGRAMS.md](./DIAGRAMS.md) for detailed flow diagrams.**

---

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB (running on localhost:27017)
- Qdrant (running on localhost:6333)
- RabbitMQ (running on localhost:5672)

### Installation

```bash
cd rag

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install package in development mode
pip install -e .
```

### Environment Variables

Create a `.env` file or export these variables:

### Running the Server

```bash
# Development server
python -m bootstrap.flask_app

```

### Running Celery Workers

```bash
# Start pipeline worker
celery -A infrastructure.celery.app worker -Q document_queue,slack_queue -l info

# Start event worker (Slack events)
celery -A infrastructure.celery.app worker -Q slack_events -l info
```

---

## Core Modules

The `core/` directory contains feature-sliced modules, each with its own domain models, ports, and services.

### Data Sources (`core/data_sources/`)

Central module for managing data source lifecycle.

| Component | Path | Purpose |
|-----------|------|---------|
| `DataSource` model | `domain/model.py` | Data source entity |
| `DataSourceRepository` port | `domain/repository.py` | Storage interface |
| `DataSourceService` | `service.py` | CRUD operations |

#### Source Types (`core/data_sources/types/`)

Source-specific processing logic organized by type:

**Document** (`types/document/`)
| Component | Purpose |
|-----------|---------|
| `DocumentProcessor` | Text extraction from PDF/Markdown |
| `DocumentPipelineHandler` | Pipeline execution for documents |
| `DocumentRegistration` | Document registration strategy |
| `FileValidationService` | Pre-upload file validation |
| Validators | Extension, size, duplicate checks |

**Slack** (`types/slack/`)
| Component | Purpose |
|-----------|---------|
| `SlackProcessor` | Message/thread processing |
| `SlackPipelineHandler` | Pipeline execution for channels |
| `SlackRegistration` | Channel registration strategy |
| `SlackChannel` model | Channel entity (`domain/channel/`) |
| `SlackEvent` model | Event entity (`domain/event/`) |
| Event handlers | Channel created, message events |
| Validators | Bot installation checks |

### Pipeline (`core/pipeline/`)

Pipeline lifecycle and execution.

| Component | Path | Purpose |
|-----------|------|---------|
| `PipelineRecord` model | `domain/model.py` | Pipeline state entity |
| `PipelineRepository` port | `domain/repository.py` | State storage interface |
| `PipelineDispatcher` port | `domain/dispatcher.py` | Async dispatch interface |
| `PipelineService` | `service.py` | Lifecycle management |
| `PipelineDispatchService` | `dispatch_service.py` | Registration + dispatch |
| `PipelineExecutor` | `executor.py` | Pipeline step execution |

### Vector (`core/vector/`)

Vector storage and embedding.

| Component | Path | Purpose |
|-----------|------|---------|
| `VectorChunk` model | `domain/model.py` | Chunk with embedding |
| `VectorRepository` port | `domain/repository.py` | Vector storage interface |
| `ContentChunker` port | `domain/chunker.py` | Chunking interface |
| `EmbeddingGenerator` port | `domain/embedder.py` | Embedding interface |
| `VectorStatsService` | `stats_service.py` | Storage statistics |

### Other Core Modules

| Module | Purpose |
|--------|---------|
| `core/retrieval/` | Vector search orchestration |
| `core/registration/` | Source registration factory & service |
| `core/validation/` | Validation pipeline framework |
| `core/monitoring/` | Pipeline metrics and logging |
| `core/pagination/` | Pagination model |
| `core/connector/` | Base connector interface |
| `core/processing/` | Base processor interface |
| `core/user/terms_approval/` | User terms acceptance |

---

## Infrastructure Layer

Concrete implementations of core ports using external technologies.

### Storage Adapters (`infrastructure/mongo/`)

| Adapter | Implements |
|---------|------------|
| `MongoPipelineRepository` | `PipelineRepository` |
| `MongoDataSourceRepository` | `DataSourceRepository` |
| `MongoMonitoringRepository` | `MonitoringRepository` |
| `MongoTermsApprovalRepository` | `TermsApprovalRepository` |
| `MongoSlackChannelRepository` | `SlackChannelRepository` (in `data_sources/`) |

### Vector Storage (`infrastructure/qdrant/`)

| Adapter | Implements |
|---------|------------|
| `QdrantVectorRepository` | `VectorRepository` |

### Source Adapters (`infrastructure/sources/`)

Source-specific infrastructure organized by type:

**Document** (`sources/document/`)
| Adapter | Purpose |
|---------|---------|
| `DocumentChunker` | PDF/Markdown chunking strategy |
| `DocumentConnector` | File loading |
| `DocumentConfig` | Document-specific settings |
| Validators | Duplicate checking adapters |

**Slack** (`sources/slack/`)
| Adapter | Purpose |
|---------|---------|
| `SlackChunker` | Conversation-aware chunking |
| `SlackConnector` | Slack API integration |
| `SlackConfig` | Slack-specific settings |
| `ThreadRetriever` | Thread message fetching |
| Validators | Bot installation checking |

### Processing Adapters (`infrastructure/embedding/`)

| Adapter | Purpose |
|---------|---------|
| `SentenceTransformerEmbedder` | Text → 384-dim vector embeddings |

### HTTP Adapters (`infrastructure/http/`)

| Blueprint | Path Prefix |
|-----------|-------------|
| `/health` | Health checks |
| `/docs` | Document operations |
| `/slack` | Slack operations |
| `/pipelines` | Pipeline management |
| `/data-sources` | Data source management |
| `/vector` | Vector statistics |
| `/settings` | Configuration |
| `/terms-approval` | User terms |

### Async Adapters (`infrastructure/celery/`)

| Adapter | Purpose |
|---------|---------|
| `CeleryPipelineDispatcher` | Dispatch pipeline tasks |
| `CelerySlackEventDispatcher` | Dispatch Slack event handlers |
| `pipeline_tasks.py` | Celery worker tasks |

---

## Dependency Injection

All dependencies are wired in `bootstrap/app_container.py` using `@lru_cache` for singleton management.

### Usage

```python
from bootstrap.app_container import (
    pipeline_service,
    data_source_service,
    retrieval_service,
)

# Services are singletons - same instance on every call
svc = pipeline_service()
result = svc.get(pipeline_id)

# Parameterized singletons
retriever = retrieval_service("DOCUMENT")  # One per source type
```

### Available Factories

```python
# Infrastructure (shared resources)
mongo_client()              # MongoDB connection pool
file_storage()              # Local file storage

# Repositories
pipeline_repository()       # Pipeline state storage
data_source_repository()    # Data source metadata
vector_repository(name)     # Vector storage (per collection)

# Services
pipeline_service()          # Pipeline lifecycle
data_source_service()       # Data source CRUD
monitoring_service()        # Metrics & logging
retrieval_service(type)     # Vector search

# Pipeline Components
embedding_generator()       # Sentence transformer
document_chunker()          # Document chunking
slack_chunker()             # Conversation chunking
document_connector()        # File loading
slack_connector(project)    # Slack API client
```

---

## API Endpoints

### Health

```
GET /health           → Service health status
```

### Documents

```
POST   /docs/upload   → Upload document(s)
GET    /docs          → List documents (paginated)
DELETE /docs/{id}     → Delete document
```

### Slack

```
POST   /slack/channels      → Register Slack channels
GET    /slack/channels      → List registered channels
DELETE /slack/channels/{id} → Remove channel
POST   /slack/events        → Slack Events API webhook
```

### Pipelines

```
GET    /pipelines           → List all pipelines
GET    /pipelines/{id}      → Get pipeline status
DELETE /pipelines/{id}      → Cancel/delete pipeline
```

### Vector Search

```
POST   /vector/search       → Semantic search
GET    /vector/stats        → Vector storage statistics
```

---

## Configuration

Configuration is managed via `config/app_config.py` with environment variable overrides.

| Config Key | Env Variable | Default | Description |
|------------|--------------|---------|-------------|
| `mongodb_ip` | `MONGODB_IP` | `0.0.0.0` | MongoDB host |
| `mongodb_port` | `MONGODB_PORT` | `27017` | MongoDB port |
| `qdrant_ip` | `QDRANT_URL` | `0.0.0.0` | Qdrant host |
| `qdrant_port` | `QDRANT_PORT` | `6333` | Qdrant port |
| `rabbitmq_ip` | `RABBITMQ_IP` | `0.0.0.0` | RabbitMQ host |
| `port` | `PORT` | `13457` | Server port |
| `upload_folder` | `UPLOAD_FOLDER` | `/app/shared` | File upload path |

---

## Data Flow

### Document Pipeline

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Upload    │────▶│  Validate &  │────▶│   Celery    │────▶│   Execute    │
│   Request   │     │   Register   │     │   Queue     │     │   Pipeline   │
└─────────────┘     └──────────────┘     └─────────────┘     └──────┬───────┘
                                                                    │
                   ┌──────────────┐     ┌─────────────┐     ┌───────▼───────┐
                   │    Store     │◀────│   Embed     │◀────│    Chunk      │
                   │   (Qdrant)   │     │   (384-dim) │     │   (500 tok)   │
                   └──────────────┘     └─────────────┘     └───────────────┘
```

### Search Flow

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐     ┌──────────────┐
│   Query     │────▶│    Embed     │────▶│   Vector    │────▶│   Return     │
│   Text      │     │    Query     │     │   Search    │     │   Results    │
└─────────────┘     └──────────────┘     └─────────────┘     └──────────────┘
```

---

## Extending

### Adding a New Data Source

1. **Core Domain**: Create `core/data_sources/types/<source>/domain/` with models
2. **Core Handler**: Implement `SourcePipelinePort` in `core/data_sources/types/<source>/pipeline_handler.py`
3. **Core Registration**: Add registration strategy in `core/data_sources/types/<source>/registration.py`
4. **Infrastructure Adapters**: Add connector, chunker in `infrastructure/sources/<source>/`
5. **Wire Dependencies**: Add factories to `bootstrap/app_container.py`
6. **HTTP Endpoints**: Create blueprint in `infrastructure/http/<source>.py`

### Swapping an Adapter

To replace Qdrant with Pinecone:

1. Create `infrastructure/pinecone/pinecone_vector_repository.py`
2. Implement `VectorRepository` interface from `core/vector/domain/repository.py`
3. Update `bootstrap/factories.py` to use new adapter
4. No changes needed in core layer ✅

---

## Project Structure

```
rag/
├── core/
│   ├── connector/domain/              # Base connector interface
│   ├── data_sources/
│   │   ├── domain/                    # DataSource model & repository port
│   │   ├── service.py                 # Data source CRUD
│   │   └── types/
│   │       ├── document/
│   │       │   ├── domain/            # Document processor
│   │       │   ├── validators/        # Extension, size, duplicate validators
│   │       │   ├── document_service.py
│   │       │   ├── file_validation_service.py
│   │       │   ├── log_parser.py
│   │       │   ├── pipeline_handler.py
│   │       │   └── registration.py
│   │       └── slack/
│   │           ├── domain/
│   │           │   ├── channel/       # SlackChannel model & repository port
│   │           │   ├── event/         # SlackEvent model & dispatcher port
│   │           │   └── processor.py
│   │           ├── event/
│   │           │   ├── handlers/      # Event handlers (channel_created, etc.)
│   │           │   ├── dispatch_service.py
│   │           │   └── service.py
│   │           ├── validators/        # Bot installation validator
│   │           ├── log_parser.py
│   │           ├── pipeline_handler.py
│   │           ├── registration.py
│   │           └── stats_service.py
│   ├── monitoring/
│   │   ├── domain/                    # Monitoring model & repository port
│   │   ├── parsing/                   # Log parsing utilities
│   │   └── service.py
│   ├── pagination/domain/             # Pagination model
│   ├── pipeline/
│   │   ├── domain/                    # Pipeline model, repository, dispatcher ports
│   │   ├── dispatch_service.py
│   │   ├── executor.py
│   │   └── service.py
│   ├── processing/domain/             # Base processor interface
│   ├── registration/
│   │   ├── domain/                    # Registration model & port
│   │   ├── base_registration.py
│   │   ├── factory.py
│   │   └── service.py
│   ├── retrieval/
│   │   └── service.py                 # Vector search orchestration
│   ├── user/terms_approval/
│   │   ├── domain/                    # Terms model & repository port
│   │   └── service.py
│   ├── validation/
│   │   ├── domain/                    # Validation model & port
│   │   └── validator.py
│   └── vector/
│       ├── domain/                    # Vector model, repository, chunker, embedder ports
│       └── stats_service.py
│
├── infrastructure/
│   ├── celery/
│   │   ├── app.py                     # Celery application
│   │   ├── pipeline_dispatcher.py     # Pipeline task dispatcher
│   │   ├── slack_event_dispatcher.py  # Slack event dispatcher
│   │   └── workers/
│   │       └── pipeline_tasks.py      # Worker task definitions
│   ├── config/
│   │   └── base_config_manager.py
│   ├── embedding/
│   │   └── sentence_transformer_embedder.py
│   ├── http/                          # Flask blueprints
│   │   ├── blueprints.py
│   │   ├── data_sources.py
│   │   ├── docs.py
│   │   ├── health.py
│   │   ├── pipelines.py
│   │   ├── settings.py
│   │   ├── slack.py
│   │   ├── terms_approval.py
│   │   └── vector.py
│   ├── mongo/
│   │   ├── data_sources/
│   │   │   └── slack_channel_repository.py
│   │   ├── data_source_repository.py
│   │   ├── monitoring_repository.py
│   │   ├── pagination_builder.py
│   │   ├── pipeline_repository.py
│   │   └── terms_approval_repository.py
│   ├── qdrant/
│   │   └── qdrant_vector_repository.py
│   ├── retrieval/
│   │   └── source_filter_resolver.py
│   ├── sources/
│   │   ├── document/
│   │   │   ├── chunker.py
│   │   │   ├── config.py
│   │   │   ├── connector.py
│   │   │   └── validator/
│   │   │       ├── duplicate_checker.py
│   │   │       └── name_duplicate_checker.py
│   │   └── slack/
│   │       ├── chunker.py
│   │       ├── config.py
│   │       ├── connector.py
│   │       ├── thread_retriever.py
│   │       ├── thread_retriever_worker.py
│   │       └── validator/
│   │           └── bot_installation_checker.py
│   ├── storage/
│   │   └── local_file_storage.py
│   └── umami/
│       └── umami_client.py
│
├── bootstrap/
│   ├── app_container.py               # Dependency injection container
│   ├── factories.py                   # Component factories
│   └── flask_app.py                   # Flask application factory
│
├── config/
│   └── app_config.py                  # Application configuration
│
├── shared/
│   └── logger.py                      # Logging utilities
│
├── requirements.txt                   # Python dependencies
├── setup.py                           # Package setup
├── DIAGRAMS.md                        # Flow diagrams
└── README.md                          # This file
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `flask` | HTTP framework |
| `qdrant-client` | Vector database client |
| `sentence-transformers` | Embedding generation |
| `docling` | Document parsing |
| `langchain` | LLM utilities |
| `celery` | Async task queue |
| `pymongo` | MongoDB driver |

---
