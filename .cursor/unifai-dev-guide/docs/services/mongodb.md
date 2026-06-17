---
service: mongodb
type: INFRA
sections:
  connections: 21
  features: 31
  job_description: 40
  architecture: 52
---

# MongoDB

> Document database

| Field | Value |
|-------|-------|
| ID | `mongodb` |
| Type | INFRA |
| Subtitle | Used by RAG, MAS, Identity, Platform, Celery |

## Connections

**Incoming:**
- `identity` → `mongodb` *(teams)*
- `rag` → `mongodb` *(metadata)*
- `celery` → `mongodb` *(status)*
- `mas` → `mongodb` *(sessions)*
- `temporal_worker` → `mongodb` *(session state)*
- `platform` → `mongodb` *(config)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses
- **Agentic AI Inventory** — Browse & configure AI building blocks
- **Overview Dashboards** — Stats & monitoring for RAG and Agentic AI
- **RAG Data Pipeline** — Ingest documents & search semantically
- **Team Workspace** — Shared team identity & real-time collaboration
- **Agentic AI Workflows** — Build & manage blueprint graphs

## Job Description

**MongoDB** is the primary metadata store for the entire system. Every application service uses it for persistence.

#### Databases & Collections

- **RAG**: `pipeline_monitoring` (pipelines, metrics, errors, logs), `data_sources` (sources, slack_channels), `users` (terms_user_approval)
- **MAS**: blueprints, sessions, resources, shares, templates (all scoped by `identity` subdocument)
- **Identity**: `users.teams` (team records with members and group membership)
- **Platform**: `config.admin_config`
- **Celery**: `celery.celery_taskmeta` (result backend)

## Architecture

Deployed as a StatefulSet in Kubernetes. Connection string configured per-service via environment variables (`MONGODB_IP`, `MONGODB_PORT`).

---

*Source: `js/data/services/mongodb.js`*
