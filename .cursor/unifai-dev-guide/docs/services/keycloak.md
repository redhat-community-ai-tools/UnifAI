---
service: keycloak
type: EXTERNAL
sections:
  connections: 21
  job_description: 26
  endpoints_4: 34
  architecture: 45
---

# Keycloak

> Identity provider (OIDC)

| Field | Value |
|-------|-------|
| ID | `keycloak` |
| Type | EXTERNAL |
| Subtitle | External IdP • OAuth2 / OpenID Connect |

## Connections

**Incoming:**
- `identity` → `keycloak` *(OIDC)*

## Job Description

**Keycloak** is the external identity provider. It manages user accounts, authentication, and SSO across applications.

- Hosts the login page (user never types credentials into UnifAI directly)
- Issues OAuth2 access tokens and refresh tokens
- Provides OIDC discovery at `/realms/{realm}/.well-known/openid-configuration`

## Endpoints (4)

### General

| Method | Path | Summary |
|--------|------|--------|
| GET | `/.well-known/openid-configuration` |  |
| GET | `/protocol/openid-connect/auth` | authorize |
| POST | `/protocol/openid-connect/token` | exchange code / refresh |
| GET | `/protocol/openid-connect/userinfo` |  |

## Architecture

Deployed externally. Identity service connects via Authlib OAuth client with `keycloak_base_url` and `keycloak_realm` config.

---

*Source: `js/data/services/keycloak.js`*
