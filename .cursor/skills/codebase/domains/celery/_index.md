---
name: celery-worker
scope: Async task execution worker for RAG pipelines
parent: ../SKILL.md
when_to_load: Working on Celery task definitions, queue configuration, or worker deployment
---

# Celery Worker

Async task execution service for the RAG pipeline. Shares the `rag/` codebase —
Celery tasks are thin wrappers that call RAG core services.

## Role

- Executes document processing pipeline stages asynchronously
- Scales horizontally via additional worker instances
- Handles task retry and failure recovery
- Keeps the RAG API responsive by offloading heavy work

## Entry Point

`rag/entrypoint.sh` with `ROLE=celery` runs:
```
celery -A infrastructure.celery.app worker -Q $CELERY_QUEUES
```

## Three Queues

| Queue | Purpose | Tasks |
|-------|---------|-------|
| `document_queue` | Document ingestion pipelines | `execute_pipeline_task` |
| `slack_queue` | Slack channel ingestion pipelines | `execute_pipeline_task` |
| `slack_events_queue` | Real-time Slack event processing | `process_slack_events_task` (3 retries) |

## Key Files

| File | Role |
|------|------|
| `rag/infrastructure/celery/app.py` | Celery app configuration |
| `rag/infrastructure/celery/workers/pipeline_tasks.py` | `execute_pipeline_task` entry point |
| `rag/infrastructure/celery/workers/slack_event_tasks.py` | `process_slack_events_task` entry point |
| `rag/infrastructure/celery/pipeline_dispatcher.py` | Routes tasks to queues |
| `global_utils/celery_app/init.py` | `CeleryApp` singleton factory |

## Task Execution Flow

```
CeleryPipelineDispatcher.dispatch(source_id, queue)
    → RabbitMQ → Celery Worker picks up task
        → execute_pipeline_task()
            → resolve dependencies from app container
            → select handler (DocumentPipelineHandler / SlackPipelineHandler)
            → PipelineExecutor.execute(handler, source)
                → collect → process → chunk → embed → store
```

## Worker Pool Configuration

- `threads` pool when using remote Docling/embedding (I/O-bound)
- `solo` pool for local processing (CPU-bound)
- Controlled by config flags: `use_remote_docling`, `use_remote_embedding`

## Dev-Guide Facts

For task details, pipeline execution classes, and worker architecture:
- **Service doc:** `unifai-dev-guide/docs/services/celery.md`
- **RAG core doc:** `unifai-dev-guide/docs/services/rag.md` (domain logic lives in RAG)
- **Source map:** `unifai-dev-guide/source-map.yaml → rag` (shared codebase)

## Relationship to RAG

All domain logic lives in RAG core components (see `../rag/SKILL.md`).
Celery tasks in `infrastructure/celery/workers/` contain NO business logic.
They resolve dependencies and delegate to domain services.
