# Core Infrastructure Component

Cross-cutting contracts shared by all MAS components. NOT a service — provides foundational models and ports.

## Architecture

```
   SESSION ──uses──→ CORE ←──uses── ELEMENTS
      │                │                │
      │         ┌──────┼──────┐        │
      │         ▼      ▼      ▼        │
      │     Identity  Ctx  ElementDeps  │
      │         │      │      │         │
      ▼         ▼      ▼      ▼         ▼
  ADAPTERS (IdentityProvider, ChannelFactory, AuthService)
```

### Structure

```
lib/mas/core/
├── identity/
│   ├── models.py             Identity, IdentityType, resolve_identity()
│   └── ports.py              IdentityProvider (ABC)
├── channels/
│   ├── protocols.py          StreamingChannel, StreamingChannelReader (ABC)
│   └── factory.py            ChannelFactory (ABC)
├── execution_context.py      ExecutionContext (frozen Pydantic)
├── element_deps.py           ElementDeps dataclass
├── enums.py                  ResourceCategory, ResourceOwnership, ResourceVisibility, EngineType, ...
├── field_hints.py            UI/schema hints: ReadOnlyHint, CardHint, SecretHint, HiddenHint, ActionHint, ...
├── auth/
│   ├── service.py            AuthService, AuthStrategyRegistry
│   ├── ports.py              AuthStrategy, HttpClient (ABCs)
│   └── credentials/          StoredCredential, CredentialStore port
└── inter_entity_messenger.py IEM protocol
```

### Key Models

**Identity:**
```python
class Identity(BaseModel):   # frozen
    type: IdentityType   # USER | TEAM | SYSTEM
    id: str
    display_name: str = ""
```

Flow: Flask decorator → service method(`identity=...`) → repository scopes → ExecutionContext carries to runtime.

**ExecutionContext:**
```python
class ExecutionContext(BaseModel):  # frozen
    identity: Identity
    scope: str = "public"
    engine_name: str = ""
    engine_handle: Optional[str] = None
    started_at: datetime
    tags: Dict[str, Any] = {}
```

Lifecycle: created at session creation → updated at staging → `holder.context` set at `lifecycle.begin()` → available to elements.

**ElementDeps (THE injection bridge):**
```python
@dataclass
class ElementDeps:
    execution_ctx: Optional[ExecutionContextHolder] = None
    auth_service: Optional[AuthService] = None
    file_retrieve_tool_factory: Optional[Callable[..., BaseTool]] = None
```

This is the SOLE mechanism for passing infrastructure into elements. Populated by `WorkflowSessionFactory.build_session()`.

### Key Contracts

| Port | Location | Adapter |
|------|----------|---------|
| `IdentityProvider` | `identity/ports.py` | `IdentityPodProvider` / `DevProvider` / `NoOpProvider` |
| `AdminConfigReaderPort` | `identity/ports.py` | `MongoAdminConfigReader` — reads the backend's `admin_config` collection read-only (see `references/adapters.md` Established Patterns) |
| `ChannelFactory` | `channels/factory.py` | `RedisChannelFactory` / `LocalChannelFactory` |
| `AuthService` | `auth/service.py` | — (uses strategy pattern internally) |
| `AuthStrategy` | `auth/ports.py` | `OAuth2Strategy` / `ApiKeyStrategy` |

### Enums

| Enum | Values | Used For |
|------|--------|----------|
| `ResourceCategory` | NODE, LLM, TOOL, PROVIDER, RETRIEVER, CONDITION, AUTH | Element spec declarations |
| `ResourceOwnership` | BUILTIN, CUSTOM | Built-in vs. user-owned resources — see `references/resources.md` |
| `ResourceVisibility` | DRAFT, PUBLIC | Built-in admin-only vs. all-users visibility — see `references/resources.md` |
| `IdentityType` | USER, TEAM | Identity scoping — there is no `SYSTEM` or `API_KEY` type. Built-in resources are owned by the creating admin's own (user) identity — see `references/resources.md`. |
| `EngineType` | LANGGRAPH, TEMPORAL | Graph engine selection |

Field hints (`ReadOnlyHint`, `CardHint`, `SecretHint`, `HiddenHint`, `ActionHint`, `ApiHint`,
`AuthHint`, `ConditionalHint`, `PropagateHint`, `FileUploadHint`) are Pydantic models in
`field_hints.py` combined via `combine_hints(...)` into a config field's `json_schema_extra`.
They drive UI rendering (which field type, masking, conditional visibility) and, for
built-in resources, configurability (`ReadOnlyHint`) and card display (`CardHint`) — see
`references/resources.md` and `references/elements.md`.

## How to Extend

### Adding a New Field to ElementDeps

1. Add optional field to `lib/mas/core/element_deps.py` with `field(default=None)`
2. Populate in `WorkflowSessionFactory.build_session()` (`session/building/workflow_session_factory.py`)
3. Wire source in `bootstrap/container.py` → pass to factory constructor
4. Element factory reads from kwargs in `create()` method
5. Elements NEVER import the adapter — only use the injected callable/interface

### Adding a New Core Port

1. Define ABC in appropriate sub-module (`identity/ports.py`, `channels/protocols.py`, etc.)
2. Create adapter in `adapters/outbound/<technology>/`
3. Wire in `bootstrap/container.py`
4. Inject into consumers via constructor

## Cross-Component Contracts

### Core → All (Identity Propagation)

```
Flask decorator → resolves Identity from token/headers
  → service method(identity=...) → embedded in SessionRecord
  → embedded in ExecutionContext → available to elements via holder
```

ALL repository queries MUST include identity scope:
```python
def find_by_id(self, session_id: str, identity: Identity) -> Optional[SessionRecord]:
    query = {"_id": session_id, **identity_q(identity)}
```

### Core → Session (ExecutionContext Lifecycle)

```
create_session(): ExecutionContext(identity, session_id, run_id, blueprint_id)
  → stored in SessionRecord.run_context
staging: updated with engine_handle (if submit)
lifecycle.begin(): holder.context = record.run_context  # NOW available
lifecycle.complete(): mark_finished()
```

Accessing `holder.context` before `lifecycle.begin()` raises RuntimeError (fail-fast).

### Core → Elements (ElementDeps Chain)

Full chain from config to element:
```
config/app_config.py: new_feature_key = ""
  → container.py: if cfg.new_feature_key: factory = lambda: NewThing(cfg.key)
  → WorkflowSessionFactory.__init__(new_factory=factory)
  → build_session(): ElementDeps(new_factory=factory)
  → SessionElementBuilder: passes deps as kwargs
  → ElementFactory.create(**kwargs): extracts new_factory from kwargs
  → Element uses factory at runtime
```

### Machine-Checkable Invariants

| ID | Rule | Violating Import Pattern | Severity |
|----|------|--------------------------|----------|
| INV-C01 | All repository queries include identity scope | Repository `find_*`/`list_*` method missing `identity` param in `adapters/outbound/**` | CRITICAL |
| INV-C02 | ExecutionContext not accessed before lifecycle.begin() | `holder.context` access outside `run()`/`submit()` flow in `lib/mas/session/**` | CRITICAL |

## Established Patterns

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `ElementDeps` as `@dataclass` with optional fields (not port ABC) | `lib/mas/core/element_deps.py` | Injection bridge is a data carrier, not a service contract; all fields are `Optional` with `None` default |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| `ElementDeps` fields | container.py + WorkflowSessionFactory + element factories | Injection chain |
| `Identity` model | Flask decorators + all repos using identity scope | Multi-tenant isolation |
| `ExecutionContext` fields | `lifecycle.begin()` + session record + holder | Lifecycle contract |
| Channel protocols | All channel adapters (Redis, Local) | Interface contract |
| `ResourceCategory` enum | Element specs + catalog + validation | Discovery system |

## Boundaries

**Owns:** identity model, execution context, element deps, streaming protocols, enums, auth contracts.
**Does NOT own:** session logic (session), element implementations (elements), graph state (engine).
