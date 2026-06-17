---
name: codebase-overview
description: >-
  Project overview and domain routing table for the UnifAI monorepo. Each domain
  has its own skill with `paths` scoping for auto-surfacing when editing relevant files.
---

# UnifAI Codebase Overview

UnifAI is a multi-service platform for building and running AI agent workflows.
The monorepo contains backend services (Python/Flask), a frontend (React/TypeScript),
shared libraries, and infrastructure tooling.

## Domain Routing Table

| Path prefix | Domain | Skill |
|-------------|--------|-------|
| `multi-agent/` | Multi-Agent System (MAS) | `domains/multi-agent/SKILL.md` |
| `rag/` | RAG Pipeline | `domains/rag/SKILL.md` |
| `shared-resources/identity/` | Identity & Auth | `domains/identity/SKILL.md` |
| `ui/client/src/` | Frontend UI | `domains/ui/SKILL.md` |
| `global_utils/` | Global Utilities | `domains/global-utils/SKILL.md` |
| `backend/` | Platform Backend | `domains/backend/SKILL.md` |
| `rag/infrastructure/celery/` | Celery Workers | `domains/celery/SKILL.md` |
| `temporal-worker/` | Temporal Workers | `domains/temporal-worker/SKILL.md` |

Domain skills are auto-surfaced via `paths` when editing files in their scope.

## Service Architecture Summary

| Service | Role | Tech Stack | Port |
|---------|------|-----------|------|
| **multi-agent** | AI agent orchestration engine | Python, Flask, MongoDB, Redis, LangGraph | 5001 |
| **rag** | Document ingestion & retrieval | Python, Flask, MongoDB, Qdrant, Celery | 5002 |
| **identity** | Auth, teams, SSO | Python, Flask, Keycloak, MongoDB | 5003 |
| **backend** (platform) | Admin config, platform API | Python, Flask, MongoDB | 5000 |
| **ui** | Web frontend | React, TypeScript, Vite, TailwindCSS | 3000 |
| **global_utils** | Shared Python library | Python (package) | — |
| **celery** | Async task workers for RAG | Python, Celery, Redis | — |
| **temporal-worker** | Distributed workflow execution | Python, Temporal | — |

## Cross-Cutting Concerns

| Concern | Where it lives |
|---------|---------------|
| Authentication | `shared-resources/identity/` + `global_utils/identity.py` |
| Configuration | Each service's `config/` + `global_utils/config/` |
| MongoDB access | Each service's `adapters/` or `infrastructure/` |
| Redis caching | `global_utils/redis/` + per-service usage |
| Message queues | RabbitMQ via Celery (`global_utils/celery_app/`) |
| Workflow orchestration | Temporal (`multi-agent/adapters/outbound/temporal/`) |

## Dev-Guide (optional factual reference)

The `.cursor/unifai-dev-guide/` directory contains service documentation with class architecture,
endpoint catalogs, port abstractions, and MongoDB/Qdrant schemas. Domain SKILL.md files
already contain compact versions of the most useful tables. The full dev-guide is available
for deeper reference:

| Resource | Description |
|----------|-------------|
| `.cursor/unifai-dev-guide/docs/services/<service>.md` | Full endpoint signatures, class graphs, collection schemas |
| `.cursor/unifai-dev-guide/source-map.yaml` | Maps services → composition roots, ports, endpoints, Mongo collections |
| `.cursor/unifai-dev-guide/topology.yaml` | Service graph, tech stacks, runtime edges |
| `.cursor/unifai-dev-guide/guide-index.yaml` | Maps code path globs → doc sections (used by `gen-docs.js`, CI) |
