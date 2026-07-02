# Architecture Design Review (ADR)

**Feature Name:** [GENIE-1618] — Long-Lived API Token Authentication for Service-to-Service and CLI Access

**Author:** Pipeline Designer Agent | **Date:** 2026-07-02 | **Priority:** High

---

## 1. Executive Summary

| Section | Details |
| :--- | :--- |
| **Problem Statement** | All authentication currently flows through browser session cookies (Keycloak → Redis → `validate_session`). This works for the UI but does not support CLI/headless scripts (which rely on the insecure `X-Authenticated-User` header hack), MCP/A2A external callers, or long-running Temporal workflows where cookies may expire mid-execution. |
| **High-Level Solution** | Introduce long-lived API tokens (configurable lifetime — weeks to months) as a second authentication path. Tokens are stored in a persistent backend (Redis, MongoDB, or Vault) keyed by a securely generated token value, resolving to the same `UserSessionData` structure used by the cookie path. The existing `validate_session` decorator in `global_utils` gains a second lookup source — check cookie first, fall back to `Authorization: Bearer <token>`. All services (RAG, MAS, Backend) benefit automatically with no per-service changes. |
| **Success Metrics** | (1) A user can generate a long-lived API token from the UI. (2) CLI scripts authenticate with `Authorization: Bearer <token>` instead of the `X-Authenticated-User` header. (3) MCP/A2A external callers can authenticate against any service endpoint. (4) Temporal background workflows use the API token for RAG calls without cookie expiry risk. (5) The `X-Authenticated-User` header fallback is removed. |

---

## 2. Affected Components

| Layer | Component | Action (New/Modified) | File Path |
| :--- | :--- | :--- | :--- |
| Shared — Auth | `validate_session` | Modified — add Bearer token lookup as fallback | `global_utils/src/global_utils/flask/decorators.py` |
| Shared — Auth | Token storage model | New — token record (token_hash, user_id, created_at, expires_at, revoked) | `global_utils/src/global_utils/redis/` or `shared-resources/identity/` |
| Identity — API | Token CRUD endpoints | New — generate, list, revoke tokens per user | `shared-resources/identity/infrastructure/http/tokens.py` |
| Identity — Domain | Token service | New — generate secure token, hash for storage, validate, revoke | `shared-resources/identity/core/token_service.py` |
| MAS — Decorators | `require_session_identity` | Modified — remove `X-Authenticated-User` fallback, rely on token path | `multi-agent/adapters/inbound/flask/decorators.py` |
| MAS — Execution | `ExecutionContextHolder` | Modified — store API token alongside session cookie for Temporal path | `multi-agent/lib/mas/core/execution_context.py` |
| MAS — Temporal | Temporal DTOs + activities | Modified — forward API token through workflow params → node executor | `adapters/temporal/models.py`, `engine/distributed/node_executor.py` |
| MAS — Retrievers | `DocsRagRetriever`, `SlackRetriever` | Modified — send Bearer token when cookie is absent | `multi-agent/lib/mas/elements/retrievers/` |
| MAS — RagClient | `RagClient` | Modified — support `Authorization: Bearer` header as alternative to cookie | `multi-agent/lib/mas/elements/providers/rag_client/client.py` |
| UI — Settings | Token management page | New — generate, copy, revoke tokens | `ui/client/src/pages/` or `ui/client/src/components/settings/` |

---

## 3. Design Details

### 3.1 Token Format and Storage

- **Token format:** Securely generated random string (e.g. `unifai_<32-byte-hex>`). Not a JWT — no claims embedded, no signature to verify. The token is an opaque lookup key.
- **Storage:** Token is hashed (SHA-256) before storage. The lookup key is `api_token:{hash}`. The stored value contains the same fields as `UserSessionData` (username, access_token placeholder, created_at, expires_at).
- **Storage backend options:**
  - **Redis** (same as session store) — simplest, consistent with existing auth flow.
  - **MongoDB** (Identity service DB) — better for long-lived tokens, survives Redis restarts.
  - **Vault** — strongest security, best for production, most complex to set up.
- **Recommendation:** MongoDB for token records (durable), with Redis cache for fast lookups.

### 3.2 Auth Flow

```
Request arrives at any Flask service
  → validate_session() is called
    → Step 1: Check Flask session cookie → extract session_id → Redis lookup
    → Step 2 (fallback): Check Authorization header for "Bearer <token>"
      → hash token → lookup in token store → resolve UserSessionData
    → Step 3 (legacy, to be removed): X-Authenticated-User header
  → On success: g.user_id is set, request proceeds
```

Both paths converge at the same point — downstream code (including RAG's `@rag_require_session`) sees `g.user_id` and `g.identity_session` regardless of which path authenticated the request.

### 3.3 Token Lifecycle

| Operation | Endpoint | Details |
| :--- | :--- | :--- |
| Generate | `POST /api/tokens/create` | Returns the raw token once (never stored in plaintext). User must copy it immediately. |
| List | `GET /api/tokens/list` | Returns token metadata (name, created_at, last_used_at, expires_at) — never the raw token. |
| Revoke | `DELETE /api/tokens/revoke` | Removes token from store. Immediately invalidates. |

### 3.4 Security Considerations

- Raw token is shown **once** at creation time. Only the hash is stored.
- Tokens should have a configurable expiry (default: 90 days). Users can set shorter or longer.
- Tokens are scoped to a user — they carry the same identity and permissions as the user's session.
- Rate limiting on token validation to prevent brute-force attacks.
- Token `last_used_at` timestamp updated on each use for auditing.
- Revocation is immediate — no grace period, no cache TTL.

### 3.5 MAS → RAG Auth Strategy

Once API tokens are available, the auth forwarding strategy for internal service calls becomes:

| Caller | Cookie available? | Token available? | Strategy |
| :--- | :--- | :--- | :--- |
| UI → RAG (browser) | Yes | No | Cookie (existing, works today) |
| UI → MAS → RAG (foreground) | Yes | No | Forward cookie (implemented in GENIE-1100 Stage 7) |
| UI → MAS → Temporal → RAG | Yes (at submit time) | Yes (if user has one) | Prefer API token (no expiry risk), fall back to cookie |
| CLI → MAS → RAG | No | Yes | Bearer token forwarded to RAG |
| MCP/A2A → MAS → RAG | No | Yes | Bearer token forwarded to RAG |

---

## 4. Implementation Stages

### Stage 1 — Token storage and service (Identity)

- Define token record model (token_hash, user_id, display_name, created_at, expires_at, last_used_at, revoked)
- Implement `TokenService` (generate, validate, revoke, list)
- Choose and implement storage backend (MongoDB recommended)

### Stage 2 — Token CRUD endpoints (Identity)

- `POST /api/tokens/create` — generate token, return raw value once
- `GET /api/tokens/list` — list user's tokens (metadata only)
- `DELETE /api/tokens/revoke` — revoke a token by ID

### Stage 3 — Extend `validate_session` (global_utils)

- Add `get_bearer_token` callback to `validate_session`
- Check `Authorization: Bearer <token>` when session cookie is absent
- Hash token, lookup in token store, resolve to `UserSessionData`
- All services (RAG, MAS, Backend) gain token auth automatically

### Stage 4 — Remove `X-Authenticated-User` header hack (MAS)

- Remove `_get_fallback_user` from `multi-agent/adapters/inbound/flask/decorators.py`
- Update CI/CD scripts (`scripts/execution_workflow.py` etc.) to use API tokens
- Update documentation in `local-development/AUTH_AND_SESSIONS.md`

### Stage 5 — Temporal path: prefer token over cookie

- Extend `ExecutionContextHolder` to carry `api_token` alongside `session_cookie`
- When both are available, prefer token (longer-lived)
- Forward through Temporal DTOs → `NodeExecutor` → `RagClient`
- `RagClient` sends `Authorization: Bearer <token>` when token is available, falls back to cookie

### Stage 6 — UI: token management

- Settings page with token generation, copy-to-clipboard, revocation
- Show token metadata (name, created, last used, expiry)
- Confirmation dialog for revocation

---

## 5. Dependencies and References

- **Predecessor:** GENIE-1100 (RAG access controls + session cookie forwarding from MAS)
- **Design reference:** `design-genie-1618.md §7` (referenced in `multi-agent/adapters/inbound/flask/decorators.py` and `shared-resources/identity/utils/auth_manager.py`)
- **Key files:**
  - `global_utils/src/global_utils/flask/decorators.py` — `validate_session`, `require_team_session`
  - `global_utils/src/global_utils/redis/session_model.py` — `UserSessionData`
  - `multi-agent/adapters/inbound/flask/decorators.py` — `_get_fallback_user` (to remove)
  - `multi-agent/lib/mas/core/execution_context.py` — `ExecutionContextHolder`
  - `multi-agent/lib/mas/elements/providers/rag_client/client.py` — `RagClient`

---

## 6. Open Questions

1. **Storage backend decision** — Redis (fast, ephemeral) vs MongoDB (durable) vs Vault (secure). Recommendation: MongoDB for records + Redis cache.
2. **Token scoping** — Should tokens be scoped to specific services or permissions, or inherit full user permissions? Recommendation: full user permissions initially, add scoping later.
3. **Team tokens** — Should teams have their own API tokens, or only individual users? If team tokens are needed, the token record needs an `identity_type` field.
4. **Token rotation** — Should there be an API to rotate (revoke + regenerate) in one call? Useful for automated rotation in CI/CD.
