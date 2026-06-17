---
name: temporal-worker-knowledge
description: >-
  Domain knowledge for the Temporal worker service. Distributed workflow execution
  for MAS sessions. Shares codebase with multi-agent/ — see MAS domain for core logic.
paths: temporal-worker/**
---

# Temporal Worker Knowledge System

Distributed workflow execution service for MAS agent sessions. Shares the `multi-agent/`
codebase — Temporal workflows and activities are adapters wrapping MAS domain services.

For domain logic, load the MAS domain skill (`../multi-agent/SKILL.md`).

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

Single task queue configured via `AppConfig.temporal_task_queue` (default `"graph-engine"`). MAS submits workflows via `TemporalSessionEngine`.

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
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/temporal_worker.md`
- **MAS core doc:** `.cursor/unifai-dev-guide/docs/services/mas.md` (domain logic lives in MAS)
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → mas` (shared codebase)

## Relationship to MAS

All domain logic lives in MAS domain components (see `../multi-agent/SKILL.md`).
Temporal workflows and activities are adapters in `adapters/inbound/temporal/` — they
resolve dependencies and delegate to domain services.

## Domain Rules

Domain-specific rules for Temporal code. For MAS domain rules see `../multi-agent/SKILL.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

### 1. Workflows Are Deterministic

Temporal workflow code must be deterministic — no random, no `datetime.now()`,
no I/O, no non-deterministic operations. All side effects go through activities.
Temporal replays workflows from history — non-determinism causes replay failures.

---

### 2. Activities Are Adapters

Activity implementations are the adapter layer for Temporal. They:
1. Receive primitive/serializable inputs
2. Resolve dependencies (via `BackgroundLifecycleHandler` or container)
3. Call MAS domain service methods
4. Return serializable outputs

Business logic NEVER lives in activity functions.

---

### 3. Idempotency Keys

Activities that have side effects (DB writes, external API calls) must use
idempotency keys to safely handle Temporal retries. Session status transitions
use check-before-write to avoid duplicate state changes.

---

### 4. ExecutionContext Propagation

`ExecutionContext` is serialized into workflow state and propagated to activities.
Activities reconstruct the context and pass it to domain services.
The context is immutable (frozen Pydantic model) — mutations produce new copies.

---

### 5. Node Isolation

Each graph node executes in its own activity with its own element instances
materialized from a mini-blueprint. This provides full isolation —
one node's failure doesn't corrupt another node's state.

---

### 6. BSP Execution Model

Graph traversal follows Bulk Synchronous Parallel (BSP):
1. Plan: identify ready nodes (all predecessors complete)
2. Execute: run ready nodes in parallel activities
3. Evaluate: check edge conditions for next superstep
4. Merge: collect results and repeat

No node runs until all its predecessors have completed their superstep.

---

### Established Patterns — Temporal Worker

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Secondary composition root in `worker.py` | `adapters/inbound/temporal/worker.py` | Temporal worker constructs activity objects from `AppContainer` parts; separate entry point needs its own wiring |
| Workflow query state (`_state`, `_current_nodes`) for observability | `GraphTraversalWorkflow` | Temporal query handlers need local state for debugging/monitoring; not domain state leaking |
| `GraphTraversal` domain class accepts callbacks (not port ABCs) | `lib/mas/engine/distributed/traversal.py` | BSP algorithm is callback-injected; ports would add ceremony for a single consumer |
