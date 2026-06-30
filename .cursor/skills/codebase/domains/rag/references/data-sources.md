# Data Sources Component

Plugin-based system for connecting to external document sources: each source type provides its own connector, processor, chunker, validator, and pipeline handler.

## Architecture

### Key Classes

| Class | File | Role |
|-------|------|------|
| `DataSourceService` | `core/data_sources/service.py` | CRUD, enrichment with pipeline stats, delete (vectors + Mongo) |
| `RegistrationService` | `core/registration/service.py` | Loops items through factory-created registrars |
| `RegistrationFactory` | `core/registration/factory.py` | Chooses `DocumentRegistration` vs `SlackRegistration` |
| `DocumentRegistration` | `core/data_sources/types/document/registration.py` | Validates and registers document sources |
| `SlackRegistration` | `core/data_sources/types/slack/registration.py` | Validates and registers Slack channel sources |
| `DocumentService` | `core/data_sources/types/document/document_service.py` | DONE-only doc listing for UI |
| `FileValidationService` | `core/data_sources/types/document/file_validation_service.py` | Pre-upload validation (extension, size, duplicates) |
| `DataSourceRepository` (ABC) | `core/data_sources/domain/repository.py` | Port: source CRUD, pagination |
| `SlackChannelRepository` (ABC) | `core/data_sources/types/slack/domain/channel/repository.py` | Port: channel CRUD, membership |

### Source-Type Plugin Model

Each source type provides:

| Component | Document type | Slack type |
|-----------|--------------|------------|
| Connector | `DocumentConnector` | `SlackConnector` |
| Processor | `DocumentProcessor` | `SlackProcessor` |
| Chunker | `PDFChunkerStrategy` | `SlackChunkerStrategy` |
| Validator(s) | `DocValidators` | `SlackValidators` |
| Pipeline handler | `DocumentPipelineHandler` | `SlackPipelineHandler` |
| Registration | `DocumentRegistration` | `SlackRegistration` |

### Pipeline Handlers (SourcePipelinePort implementations)

| Handler | File | Flow |
|---------|------|------|
| `DocumentPipelineHandler` | `core/data_sources/types/document/pipeline_handler.py` | Docling convert → chunk → embed |
| `SlackPipelineHandler` | `core/data_sources/types/slack/pipeline_handler.py` | Fetch Slack → process → chunk → embed |

## How to Extend

### Adding a New Source Type

1. Create a type directory under `core/data_sources/types/<type>/` with: `registration.py`, `pipeline_handler.py`, validators
2. Create infrastructure adapters under `infrastructure/sources/<type>/`: connector, processor, chunker
3. Register in `RegistrationFactory` — factory pattern only, no if/elif chains
4. Register handler in `get_pipeline_handler()` in `app_container.py`
5. Add Qdrant collection if vectors need a separate namespace

### Adding a New Validator

1. Implement against the source-type validator port/ABC
2. Wire into the type's `Registration` class
3. Pre-upload validators go in `FileValidationService` for document types

## Cross-Component Contracts

### Data Sources → Infrastructure (Connectors)

- `DocumentConnector` → `DocumentConverterPort` → `LocalDoclingAdapter` / `RemoteDoclingAdapter`
- `SlackConnector` → Slack Web API client, `SlackChannelRepository`, `SlackThreadRetriever`
- Connectors live in `infrastructure/sources/` — they implement domain-defined ports

### Data Sources → Infrastructure (Persistence)

- `DataSourceService` → `DataSourceRepository` → `MongoDataSourceRepository`
  - DB: `data_sources`, collection: `sources`
- `SlackStatsService` → `SlackChannelRepository` → `MongoSlackChannelRepository`
  - DB: `data_sources`, collection: `slack_channels`

### Data Sources ← Pipeline

- `PipelineExecutor` calls `SourcePipelinePort.collect()` → handler selects correct connector
- Handler receives source config, returns standardized document models
- Handler owns the full source-specific pipeline: collect → process → chunk → embed

### Registration Factory Pattern

```
PipelineDispatchService → RegistrationService → RegistrationFactory
    → DocumentRegistration (validates, checks duplicates, creates metadata)
    → SlackRegistration (validates bot installation, creates metadata)
```

Source types resolved by factory — no if/elif chains for type resolution.

### Slack Events

- `SlackEventService` (handler registry) routes events by type
- `SlackEventDispatchService` validates webhook → `SlackEventDispatcher` → `CelerySlackEventDispatcher`
- Queue: `slack_events_queue` (3 retries)

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Source-type plugin set | RegistrationFactory, get_pipeline_handler(), infrastructure adapters | Full plugin bundle must stay in sync |
| DataSource delete logic | VectorRepository cleanup, pipeline records | Delete cascades vectors + metadata |
| Registration validation | Dispatch service, API upload endpoints | Registration gates pipeline dispatch |
| Slack event handlers | SlackEventService registry, Celery task | Event routing is registry-based |

## Boundaries

- **Depends on**: infrastructure (connectors, Mongo repos, external API clients)
- **Depended on by**: pipeline (calls handlers during execution), API endpoints (CRUD)
- **Ports**: `DataSourceRepository`, `SlackChannelRepository`, `RegistrationPort`, `DataConnector`
