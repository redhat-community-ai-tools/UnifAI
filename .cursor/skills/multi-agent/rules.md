---
name: mas-rules
scope: MAS-specific architectural rules and mandatory patterns
parent: _index.md
when_to_load: Writing or reviewing code in multi-agent/
---

# MAS Architectural Rules

These rules are specific to the Multi-Agent System. For universal standards
(Pydantic, enums, naming, SOLID) see `../architecture/standards.md`.
For hexagonal boundary rules see `../architecture/hexagonal.md`.

---

## 1. The Import Law

| Code in | Can import `mas.*` | Can import `adapters/` | Can import `bootstrap/` |
|---------|-------------------|----------------------|------------------------|
| `lib/mas/` | Yes (own domain) | **Never** | **Never** |
| `adapters/` | Yes | Yes (own layer) | Never |
| `bootstrap/` | Yes | Yes | Yes (own layer) |

**Single exception**: `mas.engine.factory.GraphBuilderFactory` uses `importlib.import_module()`
to lazy-load engine implementations at runtime. This is intentional — no other dynamic
or static crossing from domain to adapters is permitted.

---

## 2. Identity Object — Always

Every operation on user-owned data accepts `Identity` from `mas.core.identity.models`.
Never raw `user_id` or `team_id` strings.

```python
class Identity(BaseModel):
    type: IdentityType   # USER | TEAM
    id: str
    display_name: str = ""
```

Identity flows through the system as:
```
Flask decorator resolves Identity → service method(identity=...) → repository scopes by identity
```

All repositories that filter by owner accept `Identity` — never separate `user_id`/`team_id` params.
`ExecutionContext` carries identity through the execution runtime into nodes.

---

## 3. Two-Phase Session Execution

Every session execution (run, stream, submit) follows two strictly ordered phases:

```
STAGE:    SessionInputProjector.apply(record, inputs) → persists → status = QUEUED
EXECUTE:  manager.get_session(id) → hydrate WorkflowSession → runner.run() → status = RUNNING → COMPLETED
```

These phases are never combined. Staging persists inputs before execution begins,
guaranteeing crash-recoverability. The `get_session()` call after staging ensures
the runtime `WorkflowSession` is always built from persisted state.

---

## 4. Session Status Machine

```
PENDING → QUEUED → RUNNING → COMPLETED
                           → FAILED
                           → CANCELLED

Shared-session extensions:
LOCKED   (reserved for execution by another caller)
IN_USE   (actively executing by another caller)
```

No status may be skipped. No backward transitions. New statuses require updating:
`SessionStatus` enum, `SessionLifecycle`, repository queries that filter by status,
and the streaming subscribe endpoint.

---

## 5. Element Auto-Discovery

Elements are discovered automatically from `lib/mas/elements/<category>/<element_name>/spec/`.
The `SpecDiscoverer` walks these directories and collects all `BaseElementSpec` subclasses.
`ElementRegistry.auto_discover()` is called once at startup.

To add a new element: create the package in the correct category directory with a `spec/spec.py`
containing a concrete `BaseElementSpec` subclass. No manual registration anywhere.

Required `ClassVar` fields on every spec:
- `category` — `ResourceCategory` enum value
- `type_key` — unique identifier string
- `name` — display name
- `description` — human description
- `config_schema` — Pydantic `BaseModel` subclass for configuration
- `factory_cls` — `BaseFactory` subclass that creates element instances

`__init_subclass__` enforces these at class definition time — missing any raises `TypeError`.

---

## 6. Service as Public API

Each domain component exposes one service class. All access from outside
the component goes through that service — never through repositories,
domain objects, or internal modules directly.

Services may depend on other services. Services never depend on other
components' repositories or internal classes.

```
Flask endpoint → current_app.container.<service> → service method
Another service → injected service reference → service method
```

---

## 7. Composition Root Wiring

All dependency wiring lives in `bootstrap/container.py`. Constructor injection only.

- Services receive their dependencies as constructor parameters
- Repositories are instantiated in container and injected into services
- Adapters implement domain-defined ports (ABCs in `repository/` or `ports.py` files)
- No service instantiates its own infrastructure dependencies
- No global state, no service locator pattern

Adding new infrastructure: define abstract port in domain → implement in `adapters/outbound/` →
wire in `container.py`.

---

## 8. Flask Endpoint Conventions

Endpoints in `adapters/inbound/flask/endpoints/` follow:

- Service access: `current_app.container.<service>`
- Input parsing: `@from_body` / `@from_query` decorators from `global_utils.helpers.apiargs`
- Auth decorators (from `inbound.flask.decorators`):
  - `@with_require_identity_authorization` — authenticates, authorizes, resolves Identity
  - `@with_authenticated_user` — validates `X-Authenticated-User` header only
  - `@with_identity` — resolves Identity without auth check
  - `@require_admin_access` — admin user gate
- Route naming: RPC-style dot-separated (`user.session.create`, `blueprint.save`)
- Streaming: `Response(generator(), mimetype="application/x-ndjson")` with `X-Accel-Buffering: no`
- Error mapping: domain exceptions → JSON with `error_type` field + HTTP status code

Endpoints are thin: parse request, call service, format response. No business logic.

---

## 9. Ports Location Convention

Domain-defined ports (abstract interfaces implemented by outbound adapters):

| Pattern | Location |
|---------|----------|
| Persistence | `lib/mas/<component>/repository/repository.py` or `repository/base.py` |
| Session execution | `lib/mas/session/execution/ports.py` |
| Identity authorization | `lib/mas/core/identity/ports.py` |
| Auth credentials | `lib/mas/core/auth/credentials/ports.py` |
| Auth strategies | `lib/mas/core/auth/ports.py` |
| Streaming channels | `lib/mas/core/channels/protocols.py` |
| Collaboration storage | `lib/mas/collaboration/ports.py` |

All use `ABC` + `@abstractmethod`. Implementations live under `adapters/outbound/`.

---

## 10. ExecutionContext Propagation

`ExecutionContext` (frozen Pydantic model in `mas.core.execution_context`) carries runtime
state through the execution path:

```python
class ExecutionContext(BaseModel):
    identity: Identity
    scope: str = "public"
    engine_name: str = ""
    engine_handle: Optional[str] = None
    started_at: datetime
    tags: Dict[str, Any] = Field(default_factory=dict)
```

Created at session creation → updated at staging → carried through `WorkflowSession` →
available to nodes via `ElementDeps`. Immutable (frozen) — mutations produce new copies
via `with_scope()`, `with_credential_user()`, `mark_active()`, `mark_finished()`.

For team-owned sessions, `tags["credential_user_id"]` stores the acting human's ID
so OAuth credential lookups target the member, not the team.
