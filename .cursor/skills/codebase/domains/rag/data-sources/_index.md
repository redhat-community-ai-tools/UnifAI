---
name: rag-data-sources
scope: Source types, connectors, document processing plugins
parent: ../_index.md
when_to_load: Working on data source connectors, document types, or source registration in rag/
---

# RAG Data Sources Component

Plugin-based system for connecting to external document sources: each source type provides its own connector, processor, chunker, validator, and pipeline handler.

## Key Classes

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

## Source-Type Plugin Model

Each source type provides:

| Component | Document type | Slack type |
|-----------|--------------|------------|
| Connector | `DocumentConnector` | `SlackConnector` |
| Processor | `DocumentProcessor` | `SlackProcessor` |
| Chunker | `PDFChunkerStrategy` | `SlackChunkerStrategy` |
| Validator(s) | `DocValidators` | `SlackValidators` |
| Pipeline handler | `DocumentPipelineHandler` | `SlackPipelineHandler` |
| Registration | `DocumentRegistration` | `SlackRegistration` |

## Pipeline Handlers (SourcePipelinePort implementations)

| Handler | File | Flow |
|---------|------|------|
| `DocumentPipelineHandler` | `core/data_sources/types/document/pipeline_handler.py` | Docling convert → chunk → embed |
| `SlackPipelineHandler` | `core/data_sources/types/slack/pipeline_handler.py` | Fetch Slack → process → chunk → embed |

## Boundaries

- **Depends on**: infrastructure (connectors, Mongo repos, external API clients)
- **Depended on by**: pipeline (calls handlers during execution), API endpoints (CRUD)
- **Ports**: `DataSourceRepository`, `SlackChannelRepository`, `RegistrationPort`, `DataConnector`
