# Scheduling Module (`mas.scheduling`)

Workflow scheduling lets users define recurring or one-off timed executions
of a blueprint. The domain is engine-agnostic: all engine interaction flows
through the `ScheduleEngine` abstract base class (`ports.py`).

## Engine Availability

| Engine | Status | Notes |
|--------|--------|-------|
| Temporal | Production | Full implementation via Temporal Schedules API |
| LangGraph (ForegroundRunner) | Not implemented | Would require an external timer (Celery Beat, Kafka, cron, etc.) to trigger ticks |

The `ForegroundRunner` path (used for local LangGraph-based execution)
does **not** have a scheduling implementation. Temporal Schedules is the
only production-ready engine at this time.

When no real engine is available, `NoOpScheduleEngine` (`noop.py`) is
injected automatically. It follows the same pattern as
`NoOpTracingService` in `mas.core.tracing`: the service always receives
a non-None engine, so no `if engine:` guards are needed. The NoOp
adapter raises `ScheduleValidationError` on `create_schedule()` and
`trigger_now()` — giving the user an immediate, clear error — while
other methods (`pause`, `resume`, `delete`, `update_schedule`) are
silent no-ops for safety against stale data.

## Implementing a New Engine

To add scheduling support for another engine, implement the
`ScheduleEngine` ABC defined in `ports.py`:

- `create_schedule(schedule) -> str` — register a timer, return an opaque handle
- `pause(engine_handle)` / `resume(engine_handle)` — toggle timer state
- `delete(engine_handle)` — remove the timer permanently
- `update_schedule(engine_handle, schedule)` — atomically replace timer config
- `trigger_now(engine_handle)` — fire one immediate tick
- `describe(engine_handle) -> ScheduleInfo` — read-back live state
- `describe_batch(engine_handles) -> BatchDescribeResult` — optional override; has a default sequential fallback

The engine must also provide an inbound mechanism (equivalent to
Temporal's `ScheduledSessionWorkflow`) that implements the
`ScheduledRunOps` protocol from `mas.session.execution.scheduled_runner`
so the domain runner can orchestrate the lifecycle:

1. `provision()` → create session + stage inputs
2. `execute(params)` → run the session workflow
3. `record(session_id, outcome, failure_reason)` → persist result

For a Celery-based implementation, for example, you'd need:

- A Celery Beat schedule entry (or `django-celery-beat` dynamic schedule) as the timer
- A Celery task that acts as the inbound adapter, implementing `ScheduledRunOps`
- A `CeleryScheduleEngine` class implementing `ScheduleEngine` to manage beat entries
