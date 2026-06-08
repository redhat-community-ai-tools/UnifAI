---
name: mas-adapters
scope: Inbound and outbound adapter layer — Flask, Temporal, Mongo, Redis, LangGraph, Gemini
parent: ../_index.md
when_to_load: Adding or modifying any adapter, endpoint, repository, or external integration
---

# Adapters

Outer ring of the hexagon. Translates between external technologies and domain ports. NO business logic.

## Dependency Graph

```
  INBOUND (things calling us)         OUTBOUND (things we call)
  ┌─────────────────────┐            ┌──────────────────────────┐
  │ flask/ → endpoints  │──→ DOMAIN  │ mongo/    → repositories │
  │ temporal/ → workflows│──→ DOMAIN  │ langgraph/→ executor     │
  └─────────────────────┘            │ temporal/ → engine       │
                                     │ channels/ → streaming    │
   All go through DOMAIN services    │ redis/    → collab store │
   (never call outbound directly)    │ auth/     → OAuth client │
                                     │ identity/ → provider     │
                                     │ gemini/   → file upload  │
                                     └──────────────────────────┘
```

## Directory Organization

**Inbound** = grouped by transport: `flask/` (HTTP), `temporal/` (workflow runtime)
**Outbound** = grouped by technology: `mongo/`, `langgraph/`, `temporal/`, `channels/`, `redis/`, `auth/`, `identity/`, `gemini/`

## Naming Conventions

| Pattern | Example |
|---------|---------|
| File name | `<domain_concept>_<role>.py` → `session_repository.py`, `file_upload_adapter.py` |
| Class name | `<Tech><DomainConcept>` → `MongoSessionRepository`, `GeminiFileUploadAdapter` |
| One file per port | Each file implements exactly ONE domain ABC |

## How to Add a New External Integration

1. Define port (ABC) in domain: `lib/mas/<component>/ports.py`
2. Create directory: `adapters/outbound/<technology>/`
3. Create `__init__.py` re-exporting the adapter class
4. Create `<concept>_adapter.py` implementing the port
5. Add config: `config/app_config.py` (empty string = disabled)
6. Wire in `bootstrap/container.py` (conditional on config)
7. Inject into domain service via constructor

## How to Add a New Flask Endpoint

1. Create/edit module in `adapters/inbound/flask/endpoints/<name>.py`
2. Create `Blueprint("<name>", __name__)`
3. Decorator stack: `@route` → `@with_require_identity_authorization` → `@from_body`
4. Handler: `current_app.container.<service>.<method>(identity, **kwargs)`
5. Register blueprint in `endpoints/__init__.py`

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Domain port signature | Adapter implementing it | Contract |
| New adapter dependency | `config/app_config.py` + `container.py` | Wiring |
| Flask endpoint response format | UI client API layer | API contract |
| Temporal workflow params | `temporal/models.py` Pydantic models | Serialization |
| New technology directory | `adapters/outbound/<tech>/__init__.py` | Import path |

## Rules (Quick Reference)

- Adapters are THIN: translate, serialize, wrap errors. No business decisions.
- Inbound NEVER calls outbound directly (always through domain service)
- Adapters NEVER import other technology directories
- Domain exceptions CAN be raised from adapters (wrap tech errors)
- Lazy imports in container ONLY for optional heavy adapters

## Boundaries

**Owns:** technology translations, connection management, serialization, error wrapping.
**Does NOT own:** business logic, domain invariants, status transitions, validation rules.
