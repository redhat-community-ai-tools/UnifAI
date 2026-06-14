---
name: global-utils-rules
scope: Shared library conventions and constraints
parent: _index.md
when_to_load: Writing or reviewing code in global_utils/
---

# Global Utils Rules

Domain-specific rules for the shared library. For universal standards see
`../../architecture/standards.md`.
For hexagonal boundary rules see `.cursor/rules/hexagonal-python.md`.

---

## 1. Backward Compatibility Is Mandatory

All public APIs in global_utils are consumed by multiple services. Any change
to function signatures, class interfaces, or behavior must be backward-compatible.
New parameters require default values. Breaking changes require a deprecation cycle.

---

## 2. No Service-Specific Logic

global_utils must remain generic. It provides infrastructure utilities, not
business logic. If logic is specific to one service, it belongs in that service.

---

## 3. Minimal External Dependencies

Every dependency added to global_utils becomes a transitive dependency of all
services. Minimize external packages. Prefer stdlib solutions where adequate.

---

## 4. Config Module Is the Single Source

All environment variable resolution for shared concerns goes through the config module.
Services extend `SharedConfig` with their own settings — they don't read `os.environ`
directly for infrastructure connection strings.

---

## 5. Port Interfaces Are Minimal

Ports in `global_utils/ports/` define minimal abstract contracts shared across services.
Keep them focused (ISP). Service-specific ports belong in the service's own domain layer.

---

## 6. Redis Key Namespace Convention

All Redis keys must be namespaced by service: `identity:{key}`, `mas:{key}`.
`global_utils/redis/` provides the client and helpers but does not own key schemas —
each service defines its own key patterns.

---

## Established Patterns — Global Utils

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `SingletonMeta` metaclass for process-wide singletons | `utils/singleton.py` — used by MAS/Backend `AppContainer`, `ElementRegistry`, `ActionRegistry` | Multi-entry-point services need guaranteed single instances; first-construction-wins |
| `AsyncBridge` global accessor (`get_async_bridge()`) | `utils/async_bridge.py` — consumed from MAS domain elements, tools, actions | Sync graph nodes calling async SDKs need a process-wide anyio portal; injection would thread through every factory |
| `SharedConfig.get_instance()` ambient singleton | `config/config.py` — all services call at bootstrap | Pydantic BaseSettings with cached instance; monorepo convention for config loading |
| `CeleryApp()` singleton in task decorators | `celery_app/init.py` — used in RAG task files | Worker entry point needs a single Celery app; `@app.task` decorator requires module-level access |
