---
name: mas-knowledge
description: >-
  MAS domain knowledge — architecture, component routing, rules, recipes.
  Use when working on any file under multi-agent/.
paths: multi-agent/**
---

# MAS Knowledge System

Orchestration engine: blueprint YAML → executable agent graph → runtime engine → streamed results.

## System Graph

```
         ┌──────────┐
         │ BOOTSTRAP│ wires everything
         └────┬─────┘
              │
    ┌─────────┼──────────┐
    ▼         ▼          ▼
┌───────┐ ┌────────┐ ┌────────┐
│SESSION │→│ELEMENTS│→│ ENGINE │    DOMAIN (lib/mas/)
└───┬───┘ └───┬────┘ └───┬────┘
    │         │           │
    ▼         ▼           ▼
┌──────┐  ┌────────────────────┐
│ CORE │  │     ADAPTERS       │    OUTER RING
└──────┘  │ flask, mongo, redis│
          │ langgraph, temporal│
          │ gemini, auth       │
          └────────────────────┘
```

## File → Component Routing

| Path prefix | Component |
|-------------|-----------|
| `lib/mas/session/` | Session |
| `lib/mas/elements/`, `catalog/`, `validation/` | Elements |
| `lib/mas/engine/`, `graph/` | Engine/Graph |
| `lib/mas/core/` | Core |
| `adapters/` | Adapters |
| `bootstrap/`, `config/` | Bootstrap |

## Component Deep-Dives

For detailed component architecture and cross-component contracts:

| Component | Reference |
|-----------|-----------|
| Session | `references/session.md` — lifecycle, two-phase execution, ports, boundaries |
| Elements | `references/elements.md` — plugin system, nodes, tools, LLMs, auto-discovery |
| Engine/Graph | `references/engine-graph.md` — GraphState channels, plan layers, compilation, executors |
| Core | `references/core.md` — identity, ExecutionContext, ElementDeps, channels, enums |
| Adapters | `references/adapters.md` — inbound/outbound structure, conventions |
| Bootstrap | `references/bootstrap.md` — composition root, config, wiring |

## Task Router

| Working on... | Load |
|---------------|------|
| Session lifecycle (create, run, submit, cancel) | `references/session.md` |
| Nodes, tools, LLMs, providers, retrievers | `references/elements.md` |
| Graph state channels, compilation, execution | `references/engine-graph.md` |
| Identity, auth, streaming, enums, ElementDeps | `references/core.md` |
| Flask endpoints, Mongo repos, new integrations | `references/adapters.md` |
| Wiring, config, startup | `references/bootstrap.md` |
| Crossing component boundaries | Both relevant `references/` files |

## Recipes

| Task | Recipe |
|------|--------|
| Add a new agent node | `recipes/add-new-node.md` |
| Add a new LLM adapter | `recipes/add-new-llm.md` |
| Add a new tool | `recipes/add-new-tool.md` |
| Add a new provider | `recipes/add-new-provider.md` |

---

## MAS Architectural Rules

### 1. The Import Law

| Code in | Can import `mas.*` | Can import `adapters/` | Can import `bootstrap/` |
|---------|-------------------|----------------------|------------------------|
| `lib/mas/` | Yes (own domain) | **Never** | **Never** |
| `adapters/` | Yes | Yes (own layer) | Never |
| `bootstrap/` | Yes | Yes | Yes (own layer) |

**Single exception**: `mas.engine.factory.GraphBuilderFactory` uses `importlib.import_module()`
to lazy-load engine implementations at runtime. No other dynamic or static crossing from domain to adapters is permitted.

### 2. Identity Object — Always

Every operation on user-owned data accepts `Identity` from `mas.core.identity.models`.
Never raw `user_id` or `team_id` strings.

```python
class Identity(BaseModel):
    type: IdentityType   # USER | TEAM
    id: str
    display_name: str = ""
```

Identity flows: Flask decorator resolves Identity → service method(identity=...) → repository scopes by identity.
All repositories that filter by owner accept `Identity`. `ExecutionContext` carries identity through execution runtime.

### 3. Two-Phase Session Execution

Every session execution follows two strictly ordered phases:

```
STAGE:    SessionInputProjector.apply(record, inputs) → persists → status = QUEUED
EXECUTE:  manager.get_session(id) → hydrate WorkflowSession → runner.run() → COMPLETED
```

These phases are never combined. Staging persists inputs before execution begins, guaranteeing crash-recoverability.

### 4. Session Status Machine

```
PENDING → QUEUED → RUNNING → COMPLETED
                           → FAILED
                           → CANCELLED
Shared-session: LOCKED, IN_USE
```

No status may be skipped. No backward transitions. New statuses require updating: `SessionStatus` enum, `SessionLifecycle`, repository queries, and the streaming subscribe endpoint.

### 5. Element Auto-Discovery

Elements are discovered from `lib/mas/elements/<category>/<element_name>/spec/`.
`SpecDiscoverer` walks these directories and collects all `BaseElementSpec` subclasses.
`ElementRegistry.auto_discover()` is called once at startup.

Required `ClassVar` fields on every spec: `category`, `type_key`, `name`, `description`, `config_schema`, `factory_cls`.

### 6. Service as Public API

Each domain component exposes one service class. All access from outside the component goes through that service — never through repositories or internal modules directly.

### 7. Composition Root Wiring

All dependency wiring lives in `bootstrap/container.py`. Constructor injection only.
No service instantiates its own infrastructure dependencies. No global state, no service locator.

### 8. Flask Endpoint Conventions

- Service access: `current_app.container.<service>`
- Auth decorators: `@with_require_identity_authorization`, `@with_authenticated_user`, `@with_identity`, `@require_admin_access`
- Route naming: RPC-style dot-separated (`user.session.create`, `blueprint.save`)
- Streaming: `Response(generator(), mimetype="application/x-ndjson")` with `X-Accel-Buffering: no`
- Endpoints are thin: parse request, call service, format response. No business logic.

### 9. Ports Location Convention

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
Ports are pure interfaces — no logging, no infrastructure imports, no concrete dependencies. Default method bodies (fallback implementations) are permitted but must stay infrastructure-free.

### 10. ExecutionContext Propagation

`ExecutionContext` (frozen Pydantic model) carries runtime state: identity, scope, engine_name, engine_handle, started_at, tags.
Created at session creation → updated at staging → carried through `WorkflowSession` → available to nodes via `ElementDeps`.
Immutable — mutations produce new copies via `with_scope()`, `mark_active()`, `mark_finished()`.

---

## Endpoint Groups

| Group | Count | Prefix | Key operations |
|-------|-------|--------|----------------|
| Sessions | 15 | `/sessions/` | create, submit, execute, cancel, subscribe, state |
| Blueprints | 11 | `/blueprints/` | save, update, get, validate, schema |
| Resources | 11 | `/resources/` | CRUD, validate, cards, schema |
| Catalog | 3 | `/catalog/` | categories, elements, specs |
| Templates | 11 | `/templates/` | CRUD, instantiate, materialize |
| Shares | 7 | `/shares/` | create, accept, decline, to_team |
| Collaboration | 14 | `/collaboration/` | join/leave, presence, edit locks |
| Graph Validation | 7 | `/graph/validation/` | topology validators |
| Actions/Stats/etc. | 11 | various | actions, statistics, credentials, health |

## Port → Adapter Wiring

| Port | Adapter | Tech |
|------|---------|------|
| `BlueprintRepository` | `MongoBlueprintRepository` | MongoDB |
| `ResourceRepository` | `MongoResourceRepository` | MongoDB |
| `SessionRepository` | `MongoSessionRepository` | MongoDB |
| `ShareRepository` | `MongoShareRepository` | MongoDB |
| `TemplateRepository` | `MongoTemplateRepository` | MongoDB |
| `CredentialStore` | `MongoCredentialStore` | MongoDB + Fernet |
| `ServerConfigStore` | `MongoServerConfigStore` | MongoDB |
| `FlowStateStore` | `RedisFlowStateStore` | Redis |
| `ChannelFactory` | `RedisChannelFactory` / `LocalChannelFactory` | Redis Streams / in-proc |
| `CollaborationStore` | `RedisCollaborationStore` | Redis |
| `BackgroundSessionEngine` | `TemporalSessionEngine` | Temporal |
| `IdentityProvider` | `IdentityPodProvider` / `DevProvider` | HTTP / in-proc |
| `AuthStrategy` | `OAuth2Strategy` / `ApiKeyStrategy` | httpx / in-proc |
| `BaseGraphBuilder` | `TemporalBuilder` / `LangGraphBuilder` | Temporal / LangGraph |

## MongoDB Collections

| Collection | Key Fields | Notable |
|------------|-----------|---------|
| blueprints | blueprint_id, identity, spec_dict, rid_refs | Unique on blueprint_id |
| workflow_sessions | run_id, identity, blueprint_id, graph_state, status | Compound identity+time index |
| resources | rid, identity, category, type, name, cfg_dict | Unique on identity+category+type+name |
| shares | share_id, sender/recipient_identity, status | TTL auto-expiry on expires_at |
| templates | template_id, draft, placeholders, metadata | Text search on name+description |
| credentials | user_id, server_identifier, tokens (encrypted) | Fernet-encrypted tokens |
| server_configs | server_identifier, client_id/secret, endpoints | OAuth client configurations |

## Factual Reference (optional)

For full endpoint signatures, class architecture, or call graphs beyond the tables above:
`.cursor/unifai-dev-guide/docs/services/mas.md`
