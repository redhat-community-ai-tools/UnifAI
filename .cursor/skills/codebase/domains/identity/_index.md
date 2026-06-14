---
name: identity-service
scope: Identity — authentication, authorization, teams, and SSO
parent: ../SKILL.md
when_to_load: Any work touching shared-resources/identity/
---

# Identity Service

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
- **Service doc:** `unifai-dev-guide/docs/services/identity.md`
- **Source map:** `unifai-dev-guide/source-map.yaml → identity`
- **Code → doc routing:** `unifai-dev-guide/guide-index.yaml` (maps `shared-resources/identity/**` to identity.md)

## Redis Keys

| Pattern | Purpose |
|---------|---------|
| `identity:{session_id}` | Session hash storage |
| `identity:groups:{user_id}` | Cached group memberships |
