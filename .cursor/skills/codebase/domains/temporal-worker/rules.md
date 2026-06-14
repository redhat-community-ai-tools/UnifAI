---
name: temporal-worker-rules
scope: Temporal worker conventions
parent: _index.md
when_to_load: Writing or reviewing Temporal workflow or activity code
---

# Temporal Worker Rules

Domain-specific rules for Temporal code. For universal standards see
`../../architecture/standards.md`. For MAS domain rules see `../multi-agent/rules.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

## 1. Workflows Are Deterministic

Temporal workflow code must be deterministic — no random, no `datetime.now()`,
no I/O, no non-deterministic operations. All side effects go through activities.
Temporal replays workflows from history — non-determinism causes replay failures.

---

## 2. Activities Are Adapters

Activity implementations are the adapter layer for Temporal. They:
1. Receive primitive/serializable inputs
2. Resolve dependencies (via `BackgroundLifecycleHandler` or container)
3. Call MAS domain service methods
4. Return serializable outputs

Business logic NEVER lives in activity functions.

---

## 3. Idempotency Keys

Activities that have side effects (DB writes, external API calls) must use
idempotency keys to safely handle Temporal retries. Session status transitions
use check-before-write to avoid duplicate state changes.

---

## 4. ExecutionContext Propagation

`ExecutionContext` is serialized into workflow state and propagated to activities.
Activities reconstruct the context and pass it to domain services.
The context is immutable (frozen Pydantic model) — mutations produce new copies.

---

## 5. Node Isolation

Each graph node executes in its own activity with its own element instances
materialized from a mini-blueprint. This provides full isolation —
one node's failure doesn't corrupt another node's state.

---

## 6. BSP Execution Model

Graph traversal follows Bulk Synchronous Parallel (BSP):
1. Plan: identify ready nodes (all predecessors complete)
2. Execute: run ready nodes in parallel activities
3. Evaluate: check edge conditions for next superstep
4. Merge: collect results and repeat

No node runs until all its predecessors have completed their superstep.

---

## Established Patterns — Temporal Worker

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Secondary composition root in `worker.py` | `adapters/inbound/temporal/worker.py` | Temporal worker constructs activity objects from `AppContainer` parts; separate entry point needs its own wiring |
| Workflow query state (`_state`, `_current_nodes`) for observability | `GraphTraversalWorkflow` | Temporal query handlers need local state for debugging/monitoring; not domain state leaking |
| `GraphTraversal` domain class accepts callbacks (not port ABCs) | `lib/mas/engine/distributed/traversal.py` | BSP algorithm is callback-injected; ports would add ceremony for a single consumer |
