# Pipeline Component

Orchestrates the full document ingestion lifecycle: registration → Celery dispatch → collection → processing → chunking → embedding → vector storage.

## Architecture

### Key Classes

| Class | File | Role |
|-------|------|------|
| `PipelineExecutor` | `core/pipeline/executor.py` | Orchestrates stages: collect → process → chunk → embed → store |
| `PipelineService` | `core/pipeline/service.py` | CRUD and status tracking for pipeline records |
| `PipelineDispatchService` | `core/pipeline/dispatch_service.py` | Registers sources then dispatches batch tasks |
| `PipelineRecord` | `core/pipeline/domain/model.py` | Aggregate root for pipeline tracking (status, stats) |
| `SourcePipelinePort` (ABC) | `core/pipeline/domain/port.py` | Port: collect/process/chunk_embed per source type |
| `PipelineTaskDispatcher` (ABC) | `core/pipeline/domain/dispatcher.py` | Port to enqueue async pipeline work |
| `PipelineRepository` (ABC) | `core/pipeline/domain/repository.py` | Port: pipeline CRUD, stats, status |

### Call Graph

```
Flask endpoint → PipelineDispatchService → RegistrationService → PipelineTaskDispatcher
                                                                        ↓
Celery task (document_queue / slack_queue) → PipelineExecutor
    → SourcePipelinePort.collect()  (DocumentPipelineHandler or SlackPipelineHandler)
    → SourcePipelinePort.process()
    → SourcePipelinePort.chunk_and_embed()
    → VectorRepository.store()
    → PipelineService.update_status()
    → MonitoringService.record_metrics()
```

### Status State Machine

```
PENDING → PROCESSING → COMPLETED
                    → FAILED
```

## How to Extend

### Adding a New Pipeline Stage

1. Extend `SourcePipelinePort` if the stage is source-type-specific; otherwise add to `PipelineExecutor`
2. Communicate between stages via Pydantic models — no raw dicts
3. Persist status transitions through `PipelineService` → `PipelineRepository`
4. Record metrics/errors via `MonitoringService` for observability

### Adding Async Dispatch for a New Source Type

1. Implement `SourcePipelinePort` for the new source type (see data-sources reference)
2. Register handler in `get_pipeline_handler()` registry in `app_container.py`
3. Add queue routing in `CeleryPipelineDispatcher` if a dedicated queue is needed
4. Add Celery task entry that resolves handler and calls `PipelineExecutor`

## Cross-Component Contracts

### Pipeline → Data Sources

- `PipelineExecutor` receives a `SourcePipelinePort` implementation (`DocumentPipelineHandler` or `SlackPipelineHandler`) selected at dispatch time
- The handler owns the full collect → process → chunk_and_embed flow for its source type
- Returns standardized results that `PipelineExecutor` persists

### Pipeline → Infrastructure (Celery)

- `PipelineDispatchService` → `PipelineTaskDispatcher` (port) → `CeleryPipelineDispatcher` (adapter)
- Dispatches to `document_queue` or `slack_queue` based on source type
- Task entry: `execute_pipeline_task()` in `infrastructure/celery/workers/pipeline_tasks.py`
- Task builds context, selects handler, calls `PipelineExecutor`

### Pipeline → Infrastructure (Mongo)

- `PipelineService` → `PipelineRepository` (port) → `MongoPipelineRepository` (adapter)
- Collection: `pipeline_monitoring.pipelines`
- Status updates, stats tracking, error recording

### Pipeline → Vector Retrieval

- After processing, `PipelineExecutor` hands off chunks via `VectorRepository.store()`
- Embedding generation happens inside the `SourcePipelinePort` handler (via `EmbeddingGenerator`)
- Vector storage is the final pipeline stage before status update

### Pipeline → Monitoring

- `PipelineExecutor` calls `MonitoringService` for metrics, errors, and log capture
- `MonitoringService` → `MonitoringRepository` → MongoDB collections: `metrics`, `errors`, `logs`

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| `PipelineRecord` status enum | `PipelineService`, Mongo queries, API responses | Status machine is shared |
| `SourcePipelinePort` contract | All pipeline handlers (document, Slack) | Port is the handler interface |
| Dispatch queue routing | Celery worker config, `CeleryPipelineDispatcher` | Queue names must match |
| `PipelineExecutor` stage order | Handlers, monitoring, vector storage | Orchestration is centralized |

## Boundaries

- **Depends on**: data-sources (source resolution via `SourcePipelinePort`), vector-retrieval (`VectorRepository`), infrastructure (Celery dispatch, Mongo persistence)
- **Depended on by**: API endpoints (trigger dispatch), Celery workers (execute pipeline)
- **Ports**: `PipelineRepository`, `PipelineTaskDispatcher`, `SourcePipelinePort`
