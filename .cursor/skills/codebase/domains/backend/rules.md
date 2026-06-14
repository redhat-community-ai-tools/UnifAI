---
name: backend-rules
scope: Platform backend conventions
parent: _index.md
when_to_load: Writing or reviewing code in backend/
---

# Backend Rules

Domain-specific rules for the platform backend. For universal standards see
`../../architecture/standards.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

## 1. Admin Config Isolation

Admin configuration is a distinct bounded context. It has its own domain models,
services, and persistence. Other services consume admin config via API calls or
shared config, never by importing backend internals.

---

## 2. Platform-Level Concerns Only

The backend service handles platform-wide operations (admin config, feature flags,
system health). Service-specific business logic belongs in its own service (MAS, RAG, etc.),
not in the platform backend.

---

## 3. Template-Driven Config Schema

Config sections are defined in `admin_config/template.py` as static definitions.
The service merges template defaults with stored overrides at read time.
New config sections are added by extending the template — not by modifying service logic.

---

## 4. Side-Effect Dispatch

Config updates can trigger side-effects via `ActionDispatcher`. The dispatch target
and endpoint are declared in the template section definition (`on_update_target`,
`on_update_endpoint`). No ad-hoc HTTP calls from the service layer.

---

## Established Patterns — Platform Backend

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `ActionDispatcher` with direct `requests.post()` — no port ABC | `admin_config/action_dispatcher.py` | Single outbound integration (RAG only); port abstraction for one consumer is over-engineering |
| Flat package layout (no `domain/`, `ports/`, `adapters/` split) | `admin_config/`, `api/flask/`, `core/` | Service has ~10 files total; hex folder ceremony would add noise without benefit |
| `current_app.container.admin_config_service` access in endpoints | `api/flask/endpoints/*.py` | Standard Flask composition — no DI framework; container is wired at startup |
| `SingletonMeta` on `AppContainer` | `core/app_container.py` | Process-wide singleton for Flask entry point; same pattern as MAS |
| Gateway-trust auth via `X-Username` / `X-User-Id` headers | Flask endpoints | Admin-only service behind gateway; no need for full Identity auth stack |
