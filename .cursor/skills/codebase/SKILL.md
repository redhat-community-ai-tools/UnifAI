---
name: codebase-navigation
description: >-
  Project map and domain routing table for the UnifAI monorepo. Identifies which
  domain skill to load based on the file being edited. Use as the entry point
  for understanding codebase structure and navigating to the correct domain knowledge.
---

# Codebase Navigation

## How to Use

1. Identify which service/domain your task involves using the routing table below
2. Load the domain's `SKILL.md` for auto-loading metadata and entry instructions
3. Follow the domain's `_index.md` for component routing within the service
4. Load `rules.md` for domain-specific patterns before writing code
5. Always load `../architecture/standards.md` for universal rules

## Project Overview

UnifAI is a multi-service platform for building and running AI agent workflows.
The monorepo contains backend services (Python/Flask), a frontend (React/TypeScript),
shared libraries, and infrastructure tooling.

## Domain Routing Table

| Path prefix | Domain | Skill location | Tier |
|-------------|--------|---------------|------|
| `multi-agent/` | Multi-Agent System (MAS) | `domains/multi-agent/SKILL.md` | Rich |
| `rag/` | RAG Pipeline | `domains/rag/SKILL.md` | Rich |
| `shared-resources/identity/` | Identity & Auth | `domains/identity/SKILL.md` | Medium |
| `ui/client/src/` | Frontend UI | `domains/ui/SKILL.md` | Medium |
| `global_utils/` | Global Utilities | `domains/global-utils/SKILL.md` | Medium |
| `backend/` | Platform Backend | `domains/backend/SKILL.md` | Light |
| `celery` worker tasks | Celery Workers | `domains/celery/SKILL.md` | Light |
| `temporal` worker tasks | Temporal Workers | `domains/temporal-worker/SKILL.md` | Light |

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

## Companion Skills

| Skill | Purpose | Location |
|-------|---------|----------|
| Architecture Standards | Universal coding rules | `../architecture/SKILL.md` |
| Pipeline | Development workflow phases | `../pipeline/SKILL.md` |
| MAS Domain | Multi-agent deep knowledge | `domains/multi-agent/SKILL.md` |

## Dev-Guide — Single Source of Truth for Facts

The `unifai-dev-guide/` directory contains auto-generated service documentation with
class architecture, endpoint catalogs, port abstractions, and MongoDB/Qdrant schemas.
Skill files provide **navigation and rules**; dev-guide docs provide **facts**.

| Service | Dev-guide doc | Source map |
|---------|--------------|------------|
| MAS | `unifai-dev-guide/docs/services/mas.md` | `unifai-dev-guide/source-map.yaml → mas` |
| RAG | `unifai-dev-guide/docs/services/rag.md` | `unifai-dev-guide/source-map.yaml → rag` |
| Identity | `unifai-dev-guide/docs/services/identity.md` | `unifai-dev-guide/source-map.yaml → identity` |
| UI | `unifai-dev-guide/docs/services/ui.md` | `unifai-dev-guide/source-map.yaml → ui` |
| Platform | `unifai-dev-guide/docs/services/platform.md` | `unifai-dev-guide/source-map.yaml → platform` |
| global_utils | `unifai-dev-guide/docs/services/global_utils.md` | `unifai-dev-guide/source-map.yaml → global_utils` |
| Celery | `unifai-dev-guide/docs/services/celery.md` | (shares RAG source map) |
| Temporal Worker | `unifai-dev-guide/docs/services/temporal_worker.md` | (shares MAS source map) |

**When to load dev-guide docs:** When you need class details, endpoint signatures, port catalogs,
MongoDB collection schemas, or call graphs that the skill `_index.md` routing tables don't cover.

**Routing index:** `unifai-dev-guide/guide-index.yaml` maps code path globs → doc file + section key.
**Structural landmarks:** `unifai-dev-guide/source-map.yaml` maps services → composition roots, ports, endpoints, Mongo collections.
**Service topology:** `unifai-dev-guide/topology.yaml` defines the service graph, tech stacks, and runtime edges.

## Cross-Cutting Concerns

| Concern | Where it lives |
|---------|---------------|
| Authentication | `shared-resources/identity/` + `global_utils/identity.py` |
| Configuration | Each service's `config/` + `global_utils/config/` |
| MongoDB access | Each service's `adapters/` or `infrastructure/` |
| Redis caching | `global_utils/redis/` + per-service usage |
| Message queues | RabbitMQ via Celery (`global_utils/celery_app/`) |
| Workflow orchestration | Temporal (`multi-agent/adapters/outbound/temporal/`) |
