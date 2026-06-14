---
name: rag-pipeline-relationships
scope: Cross-component contracts for pipeline
parent: _index.md
---

# Pipeline Relationships

## Pipeline → Data Sources

- `PipelineExecutor` receives a `SourcePipelinePort` implementation (`DocumentPipelineHandler` or `SlackPipelineHandler`) selected at dispatch time
- The handler owns the full collect → process → chunk_and_embed flow for its source type
- Returns standardized results that `PipelineExecutor` persists

## Pipeline → Infrastructure (Celery)

- `PipelineDispatchService` → `PipelineTaskDispatcher` (port) → `CeleryPipelineDispatcher` (adapter)
- Dispatches to `document_queue` or `slack_queue` based on source type
- Task entry: `execute_pipeline_task()` in `infrastructure/celery/workers/pipeline_tasks.py`
- Task builds context, selects handler, calls `PipelineExecutor`

## Pipeline → Infrastructure (Mongo)

- `PipelineService` → `PipelineRepository` (port) → `MongoPipelineRepository` (adapter)
- Collection: `pipeline_monitoring.pipelines`
- Status updates, stats tracking, error recording

## Pipeline → Vector Retrieval

- After processing, `PipelineExecutor` hands off chunks via `VectorRepository.store()`
- Embedding generation happens inside the `SourcePipelinePort` handler (via `EmbeddingGenerator`)
- Vector storage is the final pipeline stage before status update

## Pipeline → Monitoring

- `PipelineExecutor` calls `MonitoringService` for metrics, errors, and log capture
- `MonitoringService` → `MonitoringRepository` → MongoDB collections: `metrics`, `errors`, `logs`
