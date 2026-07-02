# Adapters Component

Outer ring of the hexagon. Translates between external technologies and domain ports. NO business logic.

## Architecture

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

**Inbound** = grouped by transport: `flask/` (HTTP), `temporal/` (workflow runtime)
**Outbound** = grouped by technology: `mongo/`, `langgraph/`, `temporal/`, `channels/`, `redis/`, `auth/`, `identity/`, `gemini/`

### Naming Conventions

| Pattern | Example |
|---------|---------|
| File name | `<domain_concept>_<role>.py` → `session_repository.py`, `file_upload_adapter.py` |
| Class name | `<Tech><DomainConcept>` → `MongoSessionRepository`, `GeminiFileUploadAdapter` |
| One file per port | Each file implements exactly ONE domain ABC |

## How to Extend

### Adding a New External Integration

1. Define port (ABC) in domain: `lib/mas/<component>/ports.py`
2. Create directory: `adapters/outbound/<technology>/`
3. Create `__init__.py` re-exporting the adapter class
4. Create `<concept>_adapter.py` implementing the port
5. Add config: `config/app_config.py` (empty string = disabled)
6. Wire in `bootstrap/container.py` (conditional on config)
7. Inject into domain service via constructor

### Adding a New Flask Endpoint

1. Create/edit module in `adapters/inbound/flask/endpoints/<name>.py`
2. Create `Blueprint("<name>", __name__)`
3. Decorator stack: `@route` → `@with_require_identity_authorization` → `@from_body`
4. Handler: `current_app.container.<service>.<method>(identity, **kwargs)`
5. Register blueprint in `endpoints/__init__.py`

### New Technology Directory Template

```
outbound/<technology>/
├── __init__.py              Re-export adapter classes
├── <port_a>_adapter.py      First port implementation
├── <port_b>_adapter.py      Second port (if applicable)
└── _client.py               Shared client setup (internal, _ prefix)
```

## Cross-Component Contracts

### Flask Endpoint Conventions

Decorator stack order:
```
@bp.route("/api/<service>.<action>", methods=["POST"])
@with_require_identity_authorization     # resolves Identity
@from_body({"field": fields.Str()})      # parses request body
def handler(identity, **kwargs):         # receives both
    svc = current_app.container.<service>_service
    return jsonify(svc.<action>(identity=identity, **kwargs))
```

Streaming pattern:
```python
return Response(
    with_heartbeats(channel_reader),
    mimetype="application/x-ndjson",
    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
)
```

Error mapping: `BlueprintNotFoundError` → 404, `ValidationError` → 400.

### Temporal Conventions

- Workflows implement `BackgroundSessionOps` (structural typing via Protocol)
- Lifecycle ordering lives in domain (`BackgroundSessionRunner`) — NOT in workflow
- Activities access container from worker context
- Workflow params are Pydantic models in `temporal/models.py`
- `pydantic_data_converter` handles GraphState serialization

### Outbound Adapter Patterns

Repository (Mongo):
```python
class MongoSessionRepository(SessionRepository):
    def __init__(self, mongodb_port, mongodb_ip, db_name, collection_name): ...
    def find_by_id(self, session_id, identity): ...  # scoped by identity
```

Engine (LangGraph/Temporal):
```python
class LangGraphBuilder(BaseGraphBuilder):
    def compile(self) -> BaseGraphExecutor: ...
```

### Machine-Checkable Invariants

| ID | Rule | Violating Import Pattern | Severity |
|----|------|--------------------------|----------|
| INV-A01 | Workflows never import domain services | `from mas.session` or `from mas.elements` or `from mas.engine` in `adapters/inbound/temporal/workflows/**` | CRITICAL |
| INV-A02 | Workflows never manage lifecycle | `SessionStatus` or `lifecycle.` in `adapters/inbound/temporal/workflows/**` | CRITICAL |

## Established Patterns

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `current_app.container.<service>` access in Flask endpoints | All `adapters/inbound/flask/endpoints/` | Standard Flask composition — no DI framework; container is wired at startup |
| Secondary composition wiring in Temporal worker | `adapters/inbound/temporal/worker.py` | Temporal worker builds `NodeExecutor`, `GraphNodeActivities`, `LifecycleHandler` from container parts — separate entry point needs its own wiring |
| Shared-link read endpoint (`blueprint.info.get`) without `@with_require_identity_authorization` | `adapters/inbound/flask/endpoints/blueprints.py` | Serves the PublicChat shared-link flow, which requires unauthenticated access. Authorization is enforced via `usageScope` validation (only `"public"` blueprints are usable). Reviewers should verify the shared-link validation path, not the identity auth decorator. |
| Single-ID blueprint **write** endpoints (`blueprint.update`, `remove.blueprint`, `blueprint.metadata.set`, `blueprint.prompt-shortcuts.set`) | `adapters/inbound/flask/endpoints/blueprints.py` | These are authorization-sensitive entry points. Reviewers SHOULD verify that `@with_require_identity_authorization` (or equivalent ownership check) is present at the adapter boundary. Absence of auth on these write endpoints is a finding, not an established pattern. |

## Rules

- Adapters are THIN: translate, serialize, wrap errors. No business decisions.
- Inbound NEVER calls outbound directly (always through domain service)
- Adapters NEVER import other technology directories
- Domain exceptions CAN be raised from adapters (wrap tech errors)
- Lazy imports in container ONLY for optional heavy adapters

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Domain port signature | Adapter implementing it | Contract |
| New adapter dependency | `config/app_config.py` + `container.py` | Wiring |
| Flask endpoint response format | UI client API layer | API contract |
| Temporal workflow params | `temporal/models.py` Pydantic models | Serialization |

## Boundaries

**Owns:** technology translations, connection management, serialization, error wrapping.
**Does NOT own:** business logic, domain invariants, status transitions, validation rules.
