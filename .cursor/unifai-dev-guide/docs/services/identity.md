---
service: identity
type: APP
code_root: shared-resources/identity/
sections:
  quick_reference: 28
  connections: 37
  features: 48
  job_description: 52
  endpoints_16: 77
  file_path_patterns: 100
  architecture: 110
  class_architecture: 131
---

# Identity

> Auth & session service

| Field | Value |
|-------|-------|
| ID | `identity` |
| Type | APP |
| Tech Stack | Flask, Keycloak, Redis, MongoDB, LDAP |
| Code Root | `shared-resources/identity/` |
| Subtitle | Flask • Authlib • Keycloak OIDC • Redis sessions • Team management |

## Quick Reference

| Item | Path |
|------|------|
| Code Root | `shared-resources/identity/` |
| Composition Root | `shared-resources/identity/bootstrap/factories.py` |
| Flask Factory | `shared-resources/identity/bootstrap/flask_app.py` |
| App Config | `shared-resources/identity/config/app_config.py` |

## Connections

**Incoming:**
- `ui` → `identity` *(/api3)*
- `mas` → `identity` *(team auth)*

**Outgoing:**
- `identity` → `keycloak` *(OIDC)*
- `identity` → `redis` *(sessions)*
- `identity` → `mongodb` *(teams)*

## Features

- **Team Workspace** — Shared team identity & real-time collaboration

## Job Description

The **Identity** service is the authentication and session bridge between the UI and Keycloak. It implements the OAuth2 Authorization Code flow, manages server-side sessions, and provides **team management** for shared workspaces.

#### Login Flow

- UI redirects to `/api3/auth/login?state=...`
- Nginx does a **307 redirect** to the Identity host
- Identity redirects to Keycloak's authorize endpoint
- User logs in at Keycloak
- Keycloak calls back to `/api/auth/callback`
- Identity stores tokens in Redis, redirects to UI with `?auth=success`

#### Session Storage

Tokens and user profile live in **Redis** under `identity:session:<uuid>` keys. Only the session ID is stored in the cookie. This supports multi-pod scale-out natively.

#### Team Management

Identity owns the **Team** domain: create, update, delete teams and manage membership. Teams can include individual users and LDAP/Rover groups (with cached group members). MAS calls back to Identity to verify team membership for authorization.

#### Credentials Relay

Handles OAuth popup callbacks for external tool credentials (e.g. Google) and relays them to the Multi Agent System (MAS) via `/api/credentials/callback`.

## Endpoints (16)

### General

| Method | Path | Summary |
|--------|------|--------|
| GET | `/api/auth/login` | start OIDC flow |
| GET | `/api/auth/callback` | OAuth callback |
| POST | `/api/auth/logout` | clear session + Keycloak logout |
| GET | `/api/auth/user` | current user + is_admin |
| POST | `/api/auth/refresh` | refresh access token |
| GET | `/api/auth/config` | local_auth flag for login page |
| POST | `/api/teams/team.create` | create team |
| GET | `/api/teams/teams.list` | list teams for user (userId, groupIds) |
| GET | `/api/teams/team.get` | get team by id |
| PUT | `/api/teams/team.update` | update name/members |
| DEL | `/api/teams/team.delete` | delete team (creator only) |
| GET | `/api/teams/identity.resolve` | resolve user or team identity metadata |
| GET | `/api/credentials/callback` | OAuth popup relay to MAS |
| GET | `/api/health/` |  |
| GET | `/api/health/version` |  |
| GET | `/api/protected/user.profile` | example protected route |

## File Path Patterns

| Category | Path |
|----------|------|
| Endpoints | `shared-resources/identity/adapters/inbound/flask/endpoints/*.py` |
| Composition Root | `shared-resources/identity/bootstrap/factories.py` |
| Flask Factory | `shared-resources/identity/bootstrap/flask_app.py` |
| App Config | `shared-resources/identity/config/app_config.py` |
| Mongo Adapters | `shared-resources/identity/teams/repository/mongo_repository.py` |

## Architecture

#### Design Pattern: Hexagonal Architecture

Identity follows the same **ports and adapters** pattern as the other backend services.

#### How It's Organized

- **`bootstrap/`** — App factory (`flask_app.py`), dependency wiring (`factories.py`): builds Redis client, AuthManager, registers endpoints
- **`adapters/inbound/flask/endpoints/`** — HTTP blueprints: health, protected routes, credentials callback, team routes, identity routes
- **`utils/auth_manager.py`** — Core OAuth logic: Authlib client, session store, auth routes, decorators (`require_auth`)
- **`teams/`** — Team domain: `models.py` (Team, TeamMember), `service.py` (TeamService), `repository/` (MongoTeamRepository)
- **`config/app_config.py`** — Keycloak URL, realm, client credentials, session flags, team/directory settings

#### Key Design Decisions

- Server-side session store in Redis (no tokens in cookies, keys: `identity:session:*`)
- Nginx 307 redirect pattern (browser talks to Identity directly)
- State parameter preserves original URL across the OIDC round-trip
- Optional `local_auth` dev bypass via `DevOAuthClient`

## Class Architecture

Identity is a Flask service following the same hexagonal pattern. Core auth logic lives in `AuthManager`; Redis provides session persistence via `RedisKVStore` from global_utils. The **teams** domain handles team CRUD, membership, and directory (LDAP/Rover) integration.

### Bootstrap

| Class | File | Role |
|-------|------|------|
| `create_app()` | `bootstrap/flask_app.py` | Flask factory: loads config, builds auth stack, registers endpoints |
| `build_auth_stack()` | `bootstrap/factories.py` | Builds RedisKVStore + AuthManager + TeamService |

- `create_app()` calls: `AppConfig`, `build_auth_stack`, `register_all_endpoints`, `global_utils:RequestRules`
- `create_app()` called by: `entrypoint`
- `build_auth_stack()` calls: `global_utils:build_redis_client`, `global_utils:RedisKVStore`, `AuthManager`, `TeamService`
- `build_auth_stack()` called by: `create_app()`

### Config

| Class | File | Role |
|-------|------|------|
| `AppConfig` | `config/app_config.py` | Identity-specific settings (Keycloak, session, relay, directory, team fields) |
| `LoggingConfig` | `config/logging_config.py` | Static log level/format/handler config |

- `AppConfig` calls: `global_utils:SharedConfig`
- `AppConfig` called by: `create_app()`, `AuthManager`, `credentials_bp`, `TeamService`

### Core Auth

| Class | File | Role |
|-------|------|------|
| `AuthManager` | `utils/auth_manager.py` | OAuth integration, session store, /api/auth/* routes, refresh logic, admin check |
| `DevOAuthClient` | `utils/dev_oauth_client.py` | Dev-only stub for Keycloak: fake redirect, tokens, userinfo |

- `AuthManager` calls: `AppConfig`, `authlib`, `DevOAuthClient`, `global_utils:RedisKVStore`, `global_utils:identity_session_key`
- `AuthManager` called by: `build_auth_stack()`, `require_auth`

### Teams Domain

| Class | File | Role |
|-------|------|------|
| `Team` | `teams/models.py` | Team aggregate: team_id, name, created_by, members list, timestamps |
| `TeamMember` | `teams/models.py` | Member model: user or group, with optional cached group_members |
| `TeamService` | `teams/service.py` | Team CRUD, membership checks, group member caching |
| `MongoTeamRepository` | `teams/repository/mongo_repository.py` | MongoDB persistence for teams (users.teams collection) |

### Inbound Adapters (Flask Endpoints)

| Class | File | Role |
|-------|------|------|
| `health_bp` | `adapters/inbound/flask/endpoints/health.py` | GET /api/health/ and /api/health/version |
| `team_routes` | `adapters/inbound/flask/endpoints/team_routes.py` | Team CRUD: create, list, get, update, delete |
| `identity_routes` | `adapters/inbound/flask/endpoints/identity_routes.py` | Identity resolution and membership checks (called by MAS) |
| `protected_bp` | `adapters/inbound/flask/endpoints/protected_routes.py` | GET /api/protected/user.profile (guarded by require_auth) |
| `credentials_bp` | `adapters/inbound/flask/endpoints/credentials_callback.py` | GET /api/credentials/callback — OAuth popup relay to MAS |

---

*Source: `js/data/services/identity.js`* | *Classes: `js/data-classes/identity.js`*
