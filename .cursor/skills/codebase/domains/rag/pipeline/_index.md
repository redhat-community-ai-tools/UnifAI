---
name: rag-pipeline
scope: Pipeline execution, dispatch, and status tracking
parent: ../_index.md
when_to_load: Working on pipeline execution, dispatch, or status tracking in rag/
---

# RAG Pipeline Component

Orchestrates the full document ingestion lifecycle: registration → Celery dispatch → collection → processing → chunking → embedding → vector storage.

## Key Classes

| Class | File | Role |
|-------|------|------|
| `PipelineExecutor` | `core/pipeline/executor.py` | Orchestrates stages: collect → process → chunk → embed → store |
| `PipelineService` | `core/pipeline/service.py` | CRUD and status tracking for pipeline records |
| `PipelineDispatchService` | `core/pipeline/dispatch_service.py` | Registers sources then dispatches batch tasks |
| `PipelineRecord` | `core/pipeline/domain/model.py` | Aggregate root for pipeline tracking (status, stats) |
| `SourcePipelinePort` (ABC) | `core/pipeline/domain/port.py` | Port: collect/process/chunk_embed per source type |
| `PipelineTaskDispatcher` (ABC) | `core/pipeline/domain/dispatcher.py` | Port to enqueue async pipeline work |
| `PipelineRepository` (ABC) | `core/pipeline/domain/repository.py` | Port: pipeline CRUD, stats, status |

## Call Graph

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

## Status State Machine

```
PENDING → PROCESSING → COMPLETED
                    → FAILED
```

## Boundaries

- **Depends on**: data-sources (source resolution via `SourcePipelinePort`), vector-retrieval (`VectorRepository`), infrastructure (Celery dispatch, Mongo persistence)
- **Depended on by**: API endpoints (trigger dispatch), Celery workers (execute pipeline)
- **Ports**: `PipelineRepository`, `PipelineTaskDispatcher`, `SourcePipelinePort`
