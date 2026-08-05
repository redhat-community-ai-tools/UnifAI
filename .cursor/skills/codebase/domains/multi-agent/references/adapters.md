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
3. Decorator stack: `@route` → `@with_require_identity_authorization` → `@from_body` / `@from_query`
4. Handler: `current_app.container.<service>.<method>(identity, **kwargs)` — do **not** add `userId` / `identityType` fields; team workspace is optional `teamId` on the wire (decorator reads it; keep it out of business schemas unless the endpoint is team-only like edit locks)
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
@with_require_identity_authorization     # resolves Identity from session + optional teamId
@from_body({"field": fields.Str()})      # parses request body (business fields only)
def handler(identity, **kwargs):         # receives both
    svc = current_app.container.<service>_service
    return jsonify(svc.<action>(identity=identity, **kwargs))
```

#### Workspace identity wire contracts

`@with_require_identity_authorization` / `@require_session_identity` always validates the Redis-backed session (cookie `session_id` → `identity:session:<uuid>`). Workspace ownership is then resolved as:

| Contract | Wire shape | When to use |
|----------|------------|-------------|
| **New (preferred)** | Session cookie + optional `teamId` (query or JSON body). Omit `teamId` → personal workspace from session username. | All **new** endpoints and UI API clients. Do **not** declare `userId` / `identityType` on new Flask schemas. |
| **Legacy** | `userId` + `identityType=team\|user` (when team, `userId` is the team id) | Existing blueprints/sessions/resources/etc. callers still send this. Decorator maps it via `_extract_team_id` for backward compatibility. |

**Established inconsistency:** Both contracts coexist. Schedules and collaboration edit-locks use the new `teamId` shape; most older endpoints still receive legacy `userId` + `identityType` from the UI. Reviewers MUST NOT flag either as wrong while both are supported — flag only if **new** code adds or extends the legacy pair instead of `teamId`.

UI clients may keep accepting hook fields (`userId` + `identityType` from `useWorkspaceIdentity`) locally, but for new MAS calls they should map team view → wire `teamId` (and omit both for user view) before the request leaves the API layer (see `ui/client/src/api/schedules.ts`).

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
| Dual workspace wire contracts (new `teamId` vs legacy `userId`+`identityType`) | Decorator: `adapters/inbound/flask/decorators.py` (`_extract_team_id`). New: `endpoints/schedules.py`, `endpoints/collaboration/locks.py`. Legacy UI still hits blueprints/sessions/resources/etc. | Intentional migration in progress. Both resolve to the same `Identity` object. Do not flag coexistence; do flag **new** code that reintroduces or extends the legacy pair instead of optional `teamId`. |

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
