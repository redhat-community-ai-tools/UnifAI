# Service Reference Docs

Auto-generated reference docs for each service in the UnifAI architecture.
Regenerate with: `node gen-docs.js`

## Per-Service Docs

Each file consolidates metadata, connections, features, endpoints, ports, architecture prose, class hierarchies, and key extension points into a single readable document.

| Service | File | Description |
|---------|------|-------------|
| [Browser](browser.md) | `browser.md` | End-user entry point |
| [RAG Celery Workers](celery.md) | `celery.md` | Async ingestion pipelines |
| [global_utils](global_utils.md) | `global_utils.md` | Shared lib (all backends) |
| [Identity](identity.md) | `identity.md` | Auth & session service |
| [Keycloak](keycloak.md) | `keycloak.md` | Identity provider (OIDC) |
| [Multi Agent System (MAS)](mas.md) | `mas.md` | Multi-agent orchestration |
| [MongoDB](mongodb.md) | `mongodb.md` | Document database |
| [Platform Backend](platform.md) | `platform.md` | Admin configuration service |
| [Qdrant](qdrant.md) | `qdrant.md` | Vector database |
| [RabbitMQ](rabbitmq.md) | `rabbitmq.md` | Celery message broker |
| [RAG](rag.md) | `rag.md` | Document & vector search |
| [Redis](redis.md) | `redis.md` | Streaming, sessions & collaboration |
| [Slack API](slack.md) | `slack.md` | Paused (AIA process) |
| [Temporal Server](temporal.md) | `temporal.md` | Workflow orchestration |
| [MAS Temporal Worker](temporal_worker.md) | `temporal_worker.md` | Distributed graph execution |
| [UI / Nginx](ui.md) | `ui.md` | React SPA + reverse proxy |

## Cross-Cutting Docs

| Doc | File | Description |
|-----|------|-------------|
| [Blast Radius](blast-radius.md) | `blast-radius.md` | Cross-service dependency impact analysis — service-level dependency matrix, cross-service class dependencies, base class impact rankings, high-coupling hotspots, per-service risk summaries |

## Regeneration

```bash
node gen-docs.js                     # all service docs + blast-radius
node gen-docs.js --blast-radius-only  # blast-radius only
node gen-docs.js --skip-blast-radius  # service docs only
```

All docs are generated from the live JS data in `js/data/services/*.js`, `js/data/_edges.js`, and `js/data-classes/*.js`. Do not edit them manually.
