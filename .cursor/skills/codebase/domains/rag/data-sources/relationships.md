---
name: rag-data-sources-relationships
scope: Cross-component contracts for data sources
parent: _index.md
---

# Data Sources Relationships

## Data Sources → Infrastructure (Connectors)

- `DocumentConnector` → `DocumentConverterPort` → `LocalDoclingAdapter` / `RemoteDoclingAdapter`
- `SlackConnector` → Slack Web API client, `SlackChannelRepository`, `SlackThreadRetriever`
- Connectors live in `infrastructure/sources/` — they implement domain-defined ports

## Data Sources → Infrastructure (Persistence)

- `DataSourceService` → `DataSourceRepository` → `MongoDataSourceRepository`
  - DB: `data_sources`, collection: `sources`
- `SlackStatsService` → `SlackChannelRepository` → `MongoSlackChannelRepository`
  - DB: `data_sources`, collection: `slack_channels`

## Data Sources ← Pipeline

- `PipelineExecutor` calls `SourcePipelinePort.collect()` → handler selects correct connector
- Handler receives source config, returns standardized document models
- Handler owns the full source-specific pipeline: collect → process → chunk → embed

## Registration Factory Pattern

```
PipelineDispatchService → RegistrationService → RegistrationFactory
    → DocumentRegistration (validates, checks duplicates, creates metadata)
    → SlackRegistration (validates bot installation, creates metadata)
```

Source types resolved by factory — no if/elif chains for type resolution.

## Slack Events

- `SlackEventService` (handler registry) routes events by type
- `SlackEventDispatchService` validates webhook → `SlackEventDispatcher` → `CelerySlackEventDispatcher`
- Queue: `slack_events_queue` (3 retries)
