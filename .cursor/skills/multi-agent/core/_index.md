---
name: mas-core
scope: Cross-cutting infrastructure — identity, channels, execution context, element deps, enums
parent: ../_index.md
when_to_load: Using identity, execution context, streaming channels, enums, or ElementDeps
---

# Core Infrastructure

Cross-cutting contracts shared by all MAS components. NOT a service — provides foundational models and ports.

## Dependency Graph

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

## Structure

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
├── enums.py                  ResourceCategory, EngineType
├── auth/
│   ├── service.py            AuthService, AuthStrategyRegistry
│   ├── ports.py              AuthStrategy, HttpClient (ABCs)
│   └── credentials/          StoredCredential, CredentialStore port
└── inter_entity_messenger.py IEM protocol
```

## Key Models (Single Source of Truth)

### Identity

```python
class Identity(BaseModel):   # frozen
    type: IdentityType   # USER | TEAM
    id: str
    display_name: str = ""
```

Flow: Flask decorator → service method(`identity=...`) → repository scopes → ExecutionContext carries to runtime.

### ExecutionContext

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

### ElementDeps (THE injection bridge)

```python
@dataclass
class ElementDeps:
    execution_ctx: Optional[ExecutionContextHolder] = None
    auth_service: Optional[AuthService] = None
    file_retrieve_tool_factory: Optional[Callable[..., BaseTool]] = None
```

This is the SOLE mechanism for passing infrastructure into elements. Populated by `WorkflowSessionFactory.build_session()`.

## Key Contracts

| Port | Location | Adapter |
|------|----------|---------|
| `IdentityProvider` | `identity/ports.py` | `IdentityPodProvider` / `DevProvider` / `NoOpProvider` |
| `ChannelFactory` | `channels/factory.py` | `RedisChannelFactory` / `LocalChannelFactory` |
| `AuthService` | `auth/service.py` | — (uses strategy pattern internally) |
| `AuthStrategy` | `auth/ports.py` | `OAuth2Strategy` / `ApiKeyStrategy` |

## Enums

| Enum | Values | Used For |
|------|--------|----------|
| `ResourceCategory` | NODE, LLM, TOOL, PROVIDER, RETRIEVER, CONDITION, AUTH | Element spec declarations |
| `IdentityType` | USER, TEAM, SYSTEM, API_KEY | Identity scoping |
| `EngineType` | LANGGRAPH, TEMPORAL | Graph engine selection |

## How to Add a New Field to ElementDeps

1. Add optional field to `lib/mas/core/element_deps.py` with `field(default=None)`
2. Populate in `WorkflowSessionFactory.build_session()` (`session/building/workflow_session_factory.py`)
3. Wire source in `bootstrap/container.py` → pass to factory constructor
4. Element factory reads from kwargs in `create()` method
5. Elements NEVER import the adapter — only use the injected callable/interface

## How to Add a New Core Port

1. Define ABC in appropriate sub-module (`identity/ports.py`, `channels/protocols.py`, etc.)
2. Create adapter in `adapters/outbound/<technology>/`
3. Wire in `bootstrap/container.py`
4. Inject into consumers via constructor

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
