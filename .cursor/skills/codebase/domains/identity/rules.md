---
name: identity-rules
scope: Identity-specific architectural rules
parent: _index.md
when_to_load: Writing or reviewing code in shared-resources/identity/
---

# Identity Rules

Domain-specific architectural rules. For universal standards see
`../../architecture/standards.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

## 1. Auth at the Boundary

Authentication and authorization checks happen ONLY at the inbound adapter layer
(Flask decorators: `require_auth`, `with_require_identity_authorization`).
Domain services receive already-validated identity objects —
they never perform auth checks themselves.

---

## 2. Token Opacity

Services outside identity treat tokens as opaque strings. Only the identity service
validates, decodes, or inspects token internals. Other services call identity's
validation endpoint or use `global_utils.flask.decorators.require_identity_session`.

---

## 3. Team Scoping

Team-owned resources use the team identity, not the individual user's identity.
The identity service resolves which teams a user belongs to; downstream services
scope queries by the resolved identity (user OR team).

---

## 4. Session in Redis, Not Cookies

Tokens and user profile live in Redis under `identity:session:<uuid>` keys.
Only the session ID is stored in the cookie (httpOnly, secure).
This pattern supports multi-pod scale-out natively.

---

## 5. Nginx 307 Redirect Pattern

Browser talks to Identity directly (not proxied like other services).
Nginx issues a 307 redirect to `IDENTITY_HOST`. This means Identity
must handle CORS and cookie domain correctly for the external hostname.

---

## 6. State Parameter Preservation

The `state` parameter in the OAuth login URL preserves the original
UI URL across the OIDC round-trip. The callback uses this to redirect
the user back to their intended page.

---

## Established Patterns — Identity Service

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
