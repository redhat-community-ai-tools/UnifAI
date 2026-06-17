---
service: temporal_worker
type: WORKER
code_root: multi-agent/
sections:
  connections: 27
  features: 37
  job_description: 41
  endpoints_5: 60
  architecture: 72
  class_architecture: 87
---

# MAS Temporal Worker

> Distributed graph execution

| Field | Value |
|-------|-------|
| ID | `temporal_worker` |
| Type | WORKER |
| Tech Stack | Temporal SDK, Python |
| Code Root | `multi-agent/` (same codebase as MAS) |
| Shares Codebase With | mas |
| Subtitle | Temporal SDK • Task queue: graph-engine |

## Connections

**Incoming:**
- `mas` → `temporal_worker` *(shared codebase)*

**Outgoing:**
- `temporal_worker` → `temporal` *(poll queue)*
- `temporal_worker` → `redis` *(stream events)*
- `temporal_worker` → `mongodb` *(session state)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses

## Job Description

The **Temporal Worker** is a separate process that executes blueprint graphs durably. When the Multi Agent System (MAS) submits a workflow, the Temporal Server dispatches it to this worker.

### Why Temporal?

- **Durability** — workflows survive process restarts
- **Scalability** — multiple workers can process graphs in parallel
- **Retry logic** — built-in activity retries and timeouts

### Workflow Structure

- **SessionWorkflow** — top-level orchestrator: begin → graph → complete/fail
- **GraphTraversalWorkflow** — child workflow: runs BSP supersteps, calls activities for each node

### Node Execution

Each graph node is executed as a Temporal activity. The `NodeExecutor` materializes a "mini-blueprint" for the node and runs it, streaming events via Redis.

## Endpoints (5)

### General

| Method | Path | Summary |
|--------|------|--------|
| WF | `SessionWorkflow` | orchestrates full session lifecycle |
| WF | `GraphTraversalWorkflow` | executes graph traversal |
| ACT | `execute_graph_node` | run one node's logic |
| ACT | `evaluate_condition` | check edge conditions |
| ACT | `begin_session / complete_session / fail_session` |  |

## Architecture

### Key Files

- `adapters/inbound/temporal/worker.py` — worker registration
- `adapters/inbound/temporal/workflows/session_workflow.py`
- `adapters/inbound/temporal/workflows/graph_traversal_workflow.py`
- `adapters/inbound/temporal/activities/graph_node_activities.py`
- `lib/mas/engine/distributed/node_executor.py` — materializes + runs nodes
- `lib/mas/engine/distributed/traversal.py` — BSP graph traversal

### Execution Model

Activities run in a `ThreadPoolExecutor`. Each node execution creates its own element instances from a mini-blueprint, enabling full isolation.

## Class Architecture

The Temporal Worker runs inside the MAS codebase (`multi-agent/adapters/inbound/temporal/`). It registers workflows and activities, then polls the Temporal Server for work.

### Worker Registration

| Class | File | Role |
|-------|------|------|
| `run_worker()` | `adapters/inbound/temporal/worker.py` | Registers workflows + activities on temporalio.Worker, starts polling |

- `run_worker()` calls: `mas:SessionWorkflow`, `mas:GraphTraversalWorkflow`, `mas:GraphNodeActivities`, `mas:SessionLifecycleActivities`
- `run_worker()` called by: `entrypoint`

### Workflows

| Class | File | Role |
|-------|------|------|
| `SessionWorkflow` | `adapters/inbound/temporal/workflows/session_workflow.py` | Parent: begin → graph traversal → complete/fail lifecycle |
| `GraphTraversalWorkflow` | `adapters/inbound/temporal/workflows/graph_traversal_workflow.py` | Child: BSP supersteps — plan, execute nodes, evaluate conditions, repeat |

- `SessionWorkflow` calls: `mas:BackgroundSessionRunner`, `GraphTraversalWorkflow`, `SessionLifecycleActivities`
- `SessionWorkflow` called by: `Temporal: dispatch`

### Activities

| Class | File | Role |
|-------|------|------|
| `GraphNodeActivities` | `adapters/inbound/temporal/activities/graph_node_activities.py` | Execute one graph node or evaluate edge condition |
| `SessionLifecycleActivities` | `adapters/inbound/temporal/activities/session_lifecycle_activities.py` | Begin/complete/fail session transitions via handler |

### Engine (from MAS lib)

| Class | File | Role |
|-------|------|------|
| `NodeExecutor` | `lib/mas/engine/distributed/node_executor.py` | Executes a single node: materializes mini-blueprint, runs via session factory |
| `GraphTraversal` | `lib/mas/engine/distributed/traversal.py` | BSP superstep algorithm: which nodes are ready, execute, merge, evaluate |
| `BackgroundLifecycleHandler` | `lib/mas/session/execution/lifecycle_handler.py` | Thin adapter: session manager + lifecycle + channels for activities |

- `BackgroundLifecycleHandler` calls: `mas:UserSessionManager`, `mas:SessionLifecycle`, `mas:ChannelFactory`
- `BackgroundLifecycleHandler` called by: `SessionLifecycleActivities`

---

*Source: `js/data/services/temporal_worker.js`* | *Classes: `js/data-classes/temporal_worker.js`*
