---
service: redis
type: INFRA
sections:
  connections: 21
  features: 28
  job_description: 33
  architecture: 58
---

# Redis

> Streaming, sessions & collaboration

| Field | Value |
|-------|-------|
| ID | `redis` |
| Type | INFRA |
| Subtitle | Used by MAS (Streams + Collaboration) and Identity (sessions) |

## Connections

**Incoming:**
- `identity` → `redis` *(sessions)*
- `mas` → `redis` *(streams)*
- `temporal_worker` → `redis` *(stream events)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses
- **Team Workspace** — Shared team identity & real-time collaboration

## Job Description

**Redis** serves three roles: cross-process event streaming for MAS sessions via Redis Streams, server-side session storage for the Identity service, and **team collaboration** infrastructure for MAS.

For MAS, Redis is essential in the default Background (Temporal) execution mode — it carries streaming events from distributed workers to the UI via Redis Streams. Without Redis, MAS falls back to in-process queues (foreground single-worker only). For Identity, Redis is required for session persistence. For team collaboration features, Redis is required.

#### MAS Streaming Operations

- `XADD` — write session events to a per-session stream
- `XREAD` — blocking read for event consumers
- `SADD` / `SMEMBERS` — track active sessions
- `EXPIRE` — TTL on session streams

#### Team Collaboration Operations

- **Session presence** — join/leave/heartbeat tracking with configurable TTL (default 300s)
- **Edit locks** — per-resource and per-blueprint locks with TTL (~180s) and heartbeat renewal
- **Typing indicators** — real-time typing state for team session participants
- **Team active-session index** — tracks which sessions have active participants

#### Identity Session Operations

- `SET` / `GET` — store and retrieve user sessions (`identity:session:*` keys)
- `DEL` — clear sessions on logout

## Architecture

Tuning: `redis_stream_ttl`, `redis_stream_block_ms`, `redis_stream_batch_size` in MAS `AppConfig`.

---

*Source: `js/data/services/redis.js`*
