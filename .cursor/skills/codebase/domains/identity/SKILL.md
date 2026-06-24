---
name: identity-knowledge
description: >-
  Domain knowledge for the Identity & Authentication service. Covers auth,
  teams, OAuth, SSO, and access control. Use when working on files under
  shared-resources/identity/.
paths: shared-resources/identity/**
---

# Identity Knowledge System

Authentication and session bridge between the UI and Keycloak. OAuth2 Authorization Code flow, server-side session management, and team management for shared workspaces.

## Component Routing

| Path prefix | Component | Description |
|-------------|-----------|-------------|
| `adapters/inbound/flask/endpoints/` | Flask endpoints | health, protected, credentials, teams, identity, directory |
| `utils/auth_manager.py` | Core OAuth | Authlib client, session store, `/api/auth/*` routes, `require_auth` |
| `utils/dev_oauth_client.py` | Dev Auth | Dev-only Keycloak stub |
| `teams/` | Teams domain | `models.py`, `service.py`, `repository/` |
| `bootstrap/` | Bootstrap | `flask_app.py` (factory), `factories.py` (wiring) |
| `config/` | Config | `app_config.py`, `logging_config.py`, `directory.yaml` |

## Landmarks

| Landmark | Location |
|----------|----------|
| Composition root | `shared-resources/identity/bootstrap/factories.py` |
| Flask factory | `shared-resources/identity/bootstrap/flask_app.py` |
| App config | `shared-resources/identity/config/app_config.py` |
| Endpoint registration | `shared-resources/identity/adapters/inbound/flask/endpoints/__init__.py` |
| Auth manager | `shared-resources/identity/utils/auth_manager.py` |
| Team models | `shared-resources/identity/teams/models.py` |
| Team service | `shared-resources/identity/teams/service.py` |
| Mongo adapter | `shared-resources/identity/teams/repository/mongo_repository.py` |

## Key Classes

| Class | File | Role |
|-------|------|------|
| `AuthManager` | `utils/auth_manager.py` | OAuth integration, session store, `/api/auth/*`, refresh, admin check |
| `DevOAuthClient` | `utils/dev_oauth_client.py` | Dev-only Keycloak stub (fake redirect, tokens, userinfo) |
| `Team` | `teams/models.py` | Team aggregate: id, name, created_by, members, timestamps |
| `TeamMember` | `teams/models.py` | Member model: user or group, with cached group_members |
| `TeamService` | `teams/service.py` | Team CRUD, membership checks, group member caching |
| `MongoTeamRepository` | `teams/repository/mongo_repository.py` | MongoDB: `users.teams` collection |
| `AppConfig` | `config/app_config.py` | Keycloak URL, realm, client creds, session flags |

## OAuth Login Flow

```
UI → /api3/auth/login?state=... → Nginx 307 redirect → Identity host
  → Keycloak authorize endpoint → User logs in
  → Keycloak callback → /api/auth/callback
  → Identity stores tokens in Redis (identity:session:<uuid>)
  → Redirect to UI with ?auth=success
```

## Session Storage

Tokens and user profile in **Redis** under `identity:session:<uuid>` keys.
Only session ID stored in cookie. Supports multi-pod scale-out.

## Cross-Service Integration

- `global_utils.flask.decorators.require_identity_session()` — validates sessions from Redis
- `global_utils.redis.get_identity_session()` — reads identity hash → `UserSessionData`
- MAS calls Identity via `/api/identity/resolve` and `/api/identity/is_member` for team authorization

## MongoDB

| Database | Collection | Adapter |
|----------|-----------|---------|
| `users` | `teams` | `MongoTeamRepository` |

## Dev-Guide Facts

For class architecture, endpoint signatures, and full auth flow details:
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/identity.md`
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → identity`
- **Code → doc routing:** `.cursor/unifai-dev-guide/guide-index.yaml` (maps `shared-resources/identity/**` to identity.md)

## Redis Keys

| Pattern | Purpose |
|---------|---------|
| `identity:{session_id}` | Session hash storage |
| `identity:groups:{user_id}` | Cached group memberships |

## Domain Rules

Domain-specific architectural rules. For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

### 1. Auth at the Boundary

Authentication and authorization checks happen ONLY at the inbound adapter layer
(Flask decorators: `require_auth`, `with_require_identity_authorization`).
Domain services receive already-validated identity objects —
they never perform auth checks themselves.

---

### 2. Token Opacity

Services outside identity treat tokens as opaque strings. Only the identity service
validates, decodes, or inspects token internals. Other services call identity's
validation endpoint or use `global_utils.flask.decorators.require_identity_session`.

---

### 3. Team Scoping

Team-owned resources use the team identity, not the individual user's identity.
The identity service resolves which teams a user belongs to; downstream services
scope queries by the resolved identity (user OR team).

---

### 4. Session in Redis, Not Cookies

Tokens and user profile live in Redis under `identity:session:<uuid>` keys.
Only the session ID is stored in the cookie (httpOnly, secure).
This pattern supports multi-pod scale-out natively.

---

### 5. Nginx 307 Redirect Pattern

Browser talks to Identity directly (not proxied like other services).
Nginx issues a 307 redirect to `IDENTITY_HOST`. This means Identity
must handle CORS and cookie domain correctly for the external hostname.

---

### 6. State Parameter Preservation

The `state` parameter in the OAuth login URL preserves the original
UI URL across the OIDC round-trip. The callback uses this to redirect
the user back to their intended page.

---

### Established Patterns — Identity Service

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `AuthManager` as monolithic class (inbound routes + OAuth + Redis + cross-service) | `utils/auth_manager.py` | Core OAuth hub — intentionally combines Flask routing, Authlib OAuth, Redis session, Keycloak calls; splitting would fragment the auth flow across 4 files for minimal benefit |
| Auth routes self-register on Flask app (not via blueprints) | `AuthManager.init_app()` registers `/api/auth/*` directly | OAuth callback URLs must be stable; blueprint registration would add indirection to a security-critical path |
| Service lookup via Flask extensions (`current_app.extensions["team_service"]`) | Auth route handlers in `auth_manager.py` | Composition root wires services into `app.extensions`; runtime access is needed for cross-domain auth checks |
| `AppConfig.get_instance()` at module level | `auth_manager.py` | Config needed at import time for OAuth client setup; Keycloak URLs must be known before first request |
| `utils/` as catch-all for auth code (not in `adapters/`) | `auth_manager.py`, `dev_oauth_client.py`, `user_groups_cache.py` | Pre-dates hex adoption; established layout that reviewers should not flag |
| Two DI styles: constructor injection for teams, Flask extensions for auth | `bootstrap/factories.py` (teams), `flask_app.py` (auth) | Teams follow hex properly; auth is special-cased because `AuthManager` owns the Flask app lifecycle |
| `DevOAuthClient` as Keycloak stub in utils (not adapters) | `utils/dev_oauth_client.py` | Dev-only test double; colocation with `AuthManager` is intentional |
