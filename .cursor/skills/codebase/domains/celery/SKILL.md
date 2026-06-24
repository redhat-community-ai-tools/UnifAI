---
name: celery-knowledge
description: >-
  Domain knowledge for the Celery worker service. Async task execution for RAG
  pipeline processing. Shares codebase with rag/ — see RAG domain for core logic.
paths: rag/infrastructure/celery/**
---

# Celery Worker Knowledge System

Async task execution service for the RAG pipeline. Shares the `rag/` codebase —
Celery tasks are thin wrappers that call RAG core services.

For domain logic, load the RAG domain skill (`../rag/SKILL.md`).

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

```text
CeleryPipelineDispatcher.dispatch(source_type, source_data)
    → derive queue from source_type (e.g. "document" → document_queue)
    → send_task() → RabbitMQ → Celery Worker picks up task
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
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/celery.md`
- **RAG core doc:** `.cursor/unifai-dev-guide/docs/services/rag.md` (domain logic lives in RAG)
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → rag` (shared codebase)

## Relationship to RAG

All domain logic lives in RAG core components (see `../rag/SKILL.md`).
Celery tasks in `infrastructure/celery/workers/` contain NO business logic.
They resolve dependencies and delegate to domain services.

## Domain Rules

Domain-specific rules for Celery tasks. For RAG domain rules see `../rag/SKILL.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

### 1. Tasks Are Thin

Celery task functions contain NO business logic. They:
1. Resolve dependencies (from app container)
2. Call a single domain service method (`PipelineExecutor`)
3. Return the result

All logic lives in the RAG core services.

---

### 2. Idempotency

All tasks must be idempotent — safe to retry without side effects.
Use unique task IDs and check-before-write patterns.
`process_slack_events_task` is configured with 3 retries.

---

### 3. Serialization Safety

Task arguments must be JSON-serializable primitives (str, int, list, dict).
Never pass complex objects or model instances as task arguments.
Pass IDs and let the task resolve objects from the database.

---

### 4. Queue Routing

Tasks are routed to specific queues by source type:
- Document sources → `document_queue`
- Slack sources → `slack_queue`
- Slack events → `slack_events_queue`

Queue routing is handled by `CeleryPipelineDispatcher` — task code does not choose queues.

---

### Established Patterns — Celery Workers

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Direct imports from `bootstrap.app_container` in task functions | `rag/infrastructure/celery/workers/pipeline_tasks.py`, `slack_event_tasks.py` | Workers are driving adapters; composition root is the canonical dependency source |
| `CeleryApp()` singleton for task registration | Task decorators in worker modules | Celery framework requirement — app must exist at import time for `@app.task` |
