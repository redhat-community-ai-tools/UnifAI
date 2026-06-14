---
name: celery-rules
scope: Celery worker conventions
parent: _index.md
when_to_load: Writing or reviewing Celery task code
---

# Celery Worker Rules

Domain-specific rules for Celery tasks. For universal standards see
`../../architecture/standards.md`. For RAG domain rules see `../rag/rules.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

## 1. Tasks Are Thin

Celery task functions contain NO business logic. They:
1. Resolve dependencies (from app container)
2. Call a single domain service method (`PipelineExecutor`)
3. Return the result

All logic lives in the RAG core services.

---

## 2. Idempotency

All tasks must be idempotent — safe to retry without side effects.
Use unique task IDs and check-before-write patterns.
`process_slack_events_task` is configured with 3 retries.

---

## 3. Serialization Safety

Task arguments must be JSON-serializable primitives (str, int, list, dict).
Never pass complex objects or model instances as task arguments.
Pass IDs and let the task resolve objects from the database.

---

## 4. Queue Routing

Tasks are routed to specific queues by source type:
- Document sources → `document_queue`
- Slack sources → `slack_queue`
- Slack events → `slack_events_queue`

Queue routing is handled by `CeleryPipelineDispatcher` — task code does not choose queues.

---

## Established Patterns — Celery Workers

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Direct imports from `bootstrap.app_container` in task functions | `rag/infrastructure/celery/workers/pipeline_tasks.py`, `slack_event_tasks.py` | Workers are driving adapters; composition root is the canonical dependency source |
| `CeleryApp()` singleton for task registration | Task decorators in worker modules | Celery framework requirement — app must exist at import time for `@app.task` |
