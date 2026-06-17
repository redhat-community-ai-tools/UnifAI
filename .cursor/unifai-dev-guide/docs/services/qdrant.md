---
service: qdrant
type: INFRA
sections:
  connections: 21
  features: 27
  job_description: 32
  architecture: 43
---

# Qdrant

> Vector database

| Field | Value |
|-------|-------|
| ID | `qdrant` |
| Type | INFRA |
| Subtitle | Used by RAG only • Cosine similarity |

## Connections

**Incoming:**
- `rag` → `qdrant` *(vectors)*
- `celery` → `qdrant` *(upsert)*

## Features

- **Overview Dashboards** — Stats & monitoring for RAG and Agentic AI
- **RAG Data Pipeline** — Ingest documents & search semantically

## Job Description

**Qdrant** stores vector embeddings for semantic search. RAG creates collections per source type (e.g., `document_data`, `slack_data`).

### Operations

- **Upsert** — batches of 100 points (vector + text + metadata)
- **Query** — vector similarity search with optional metadata filters
- **Delete** — by point IDs or source_id filter
- **Count** — exact or approximate collection stats

## Architecture

Collections are auto-created with cosine distance metric and payload indexes on `metadata.source_type`, `metadata.channel_name`, `metadata.source_id`.

---

*Source: `js/data/services/qdrant.js`*
