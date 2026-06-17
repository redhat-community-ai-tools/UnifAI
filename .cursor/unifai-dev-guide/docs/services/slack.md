---
service: slack
type: DISABLED
sections:
  connections: 21
  job_description: 26
  endpoints_4: 33
  architecture: 44
---

# Slack API

> Paused (AIA process)

| Field | Value |
|-------|-------|
| ID | `slack` |
| Type | DISABLED |
| Subtitle | External • Slack Web API + Events API |

## Connections

**Outgoing:**
- `slack` → `rag` *(paused)*

## Job Description

**Slack** integration works in two directions:

- **Outbound** — RAG calls the Slack Web API to fetch channels, message history, and user info
- **Inbound** — Slack's Events API sends webhooks to `POST /api/slack/events` for real-time updates

## Endpoints (4)

### General

| Method | Path | Summary |
|--------|------|--------|
| GET | `auth.test` | verify bot token |
| GET | `conversations.list` | list channels |
| GET | `conversations.history` | fetch messages |
| GET | `users.info` | user details |

## Architecture

Authentication via bot token and user token stored in RAG config (`slack_bot_token`, `slack_user_token`).

---

*Source: `js/data/services/slack.js`*
