---
service: rabbitmq
type: INFRA
sections:
  connections: 21
  features: 27
  job_description: 31
  architecture: 41
---

# RabbitMQ

> Celery message broker

| Field | Value |
|-------|-------|
| ID | `rabbitmq` |
| Type | INFRA |
| Subtitle | AMQP broker for RAG Celery workers |

## Connections

**Incoming:**
- `rag` → `rabbitmq` *(enqueue)*
- `celery` → `rabbitmq` *(consume)*

## Features

- **RAG Data Pipeline** — Ingest documents & search semantically

## Job Description

**RabbitMQ** serves as the Celery message broker, carrying task messages from the RAG to Celery workers.

#### Queues

- `document_queue` — document ingestion tasks
- `slack_queue` — Slack channel ingestion tasks
- `slack_events_queue` — real-time Slack event handling

## Architecture

Configured via `rabbitmq_ip`, `rabbitmq_port`, `broker_user_name`, `broker_password` in `AppConfig`.

---

*Source: `js/data/services/rabbitmq.js`*
