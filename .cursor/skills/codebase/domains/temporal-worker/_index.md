---
name: temporal-worker
scope: Distributed workflow execution for MAS sessions
parent: ../SKILL.md
when_to_load: Working on Temporal workflows, activities, or distributed engine execution
---

# Temporal Worker

Distributed workflow execution service for MAS agent sessions. Shares the `multi-agent/`
codebase — Temporal workflows and activities are adapters wrapping MAS domain services.

## Role

- Executes agent session workflows via Temporal (durable, crash-recoverable)
- Runs distributed graph execution across workers
- Handles workflow lifecycle (start, signal, cancel, timeout)
- Provides Temporal replay guarantees for long-running agent sessions

## Key Files

| File | Role |
|------|------|
| `adapters/inbound/temporal/worker.py` | Worker registration: workflows + activities |
| `adapters/inbound/temporal/workflows/session_workflow.py` | `SessionWorkflow` — top-level lifecycle |
| `adapters/inbound/temporal/workflows/graph_traversal_workflow.py` | `GraphTraversalWorkflow` — BSP supersteps |
| `adapters/inbound/temporal/activities/graph_node_activities.py` | `GraphNodeActivities` — execute one node |
| `adapters/inbound/temporal/activities/session_lifecycle_activities.py` | Begin/complete/fail transitions |
| `lib/mas/engine/distributed/node_executor.py` | `NodeExecutor` — materializes mini-blueprint, runs node |
| `lib/mas/engine/distributed/traversal.py` | `GraphTraversal` — BSP superstep algorithm |
| `lib/mas/session/execution/lifecycle_handler.py` | `BackgroundLifecycleHandler` — thin adapter for activities |

## Workflow Structure

```
Temporal Server → dispatch → SessionWorkflow (parent)
    → begin_session activity
    → GraphTraversalWorkflow (child) — BSP supersteps:
        → plan: which nodes are ready?
        → execute_graph_node activities (parallel per node)
        → evaluate_condition activities
        → merge results → repeat
    → complete_session / fail_session activity
```

## Activities (Temporal adapters)

| Activity | Class | Purpose |
|----------|-------|---------|
| `execute_graph_node` | `GraphNodeActivities` | Run one node via `NodeExecutor` |
| `evaluate_condition` | `GraphNodeActivities` | Check edge conditions |
| `begin_session` | `SessionLifecycleActivities` | Session status → RUNNING |
| `complete_session` | `SessionLifecycleActivities` | Session status → COMPLETED |
| `fail_session` | `SessionLifecycleActivities` | Session status → FAILED |

## Task Queue

Single task queue: `graph-engine`. MAS submits workflows via `TemporalSessionEngine`.

## Execution Model

Activities run in a `ThreadPoolExecutor`. Each node execution creates its own element
instances from a mini-blueprint, enabling full isolation between node runs.

## Key MAS Components Used

| MAS Component | Used For |
|---------------|----------|
| `session/` | Workflow lifecycle maps to session lifecycle |
| `engine/distributed/` | `NodeExecutor`, `GraphTraversal` — BSP execution |
| `core/execution_context` | `ExecutionContext` propagated through workflow → activities |
| `session/execution/lifecycle_handler` | `BackgroundLifecycleHandler` wraps session operations |

## Dev-Guide Facts

For workflow/activity details, engine classes, and session lifecycle:
- **Service doc:** `unifai-dev-guide/docs/services/temporal_worker.md`
- **MAS core doc:** `unifai-dev-guide/docs/services/mas.md` (domain logic lives in MAS)
- **Source map:** `unifai-dev-guide/source-map.yaml → mas` (shared codebase)

## Relationship to MAS

All domain logic lives in MAS domain components (see `../multi-agent/SKILL.md`).
Temporal workflows and activities are adapters in `adapters/inbound/temporal/` — they
resolve dependencies and delegate to domain services.
