---
service: temporal
type: INFRA
sections:
  connections: 21
  features: 27
  job_description: 31
  architecture: 42
---

# Temporal Server

> Workflow orchestration

| Field | Value |
|-------|-------|
| ID | `temporal` |
| Type | INFRA |
| Subtitle | Default engine • Durable workflow execution for MAS |

## Connections

**Incoming:**
- `mas` → `temporal` *(submit WF)*
- `temporal_worker` → `temporal` *(poll queue)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses

## Job Description

**Temporal** is the default execution engine for MAS (`engine_name=temporal`). It provides durable, distributed workflow execution. Without it, MAS falls back to in-process foreground execution via LangGraph.

### Benefits

- Workflows survive process crashes and restarts
- Built-in retry policies for activities
- Horizontal scaling via multiple workers on the same task queue
- Visibility UI for workflow debugging

## Architecture

Connection configured via `temporal_host`, `temporal_namespace` in MAS `AppConfig`. Worker registered in `adapters/inbound/temporal/worker.py`.

---

*Source: `js/data/services/temporal.js`*
