---
name: add-new-provider
scope: Step-by-step recipe for adding a new provider to MAS
parent: ../SKILL.md
when_to_load: Creating a new provider element under lib/mas/elements/providers/
---

# Add a New Provider

Providers are integration clients that nodes use to connect to external services
(MCP servers, RAG backends, A2A agents). Unlike LLMs and tools, there is **no
abstract `BaseProvider`** — each provider defines its own API. They share only
the element registration pattern (spec + factory + config).

## Package Structure

Create the following tree under `lib/mas/elements/providers/<name>/`:

```
<name>/
├── identifiers.py              # TYPE constant + META dataclass
├── config.py                   # Pydantic config extending ProviderBaseConfig
├── <name>_provider.py          # Provider implementation (main class)
├── <name>_factory.py           # BaseFactory subclass
├── spec/
│   ├── __init__.py             # re-exports the spec class
│   └── spec.py                 # BaseElementSpec subclass
└── (optional)
    ├── client.py               # Low-level protocol/transport client
    ├── converter.py            # Domain ↔ SDK type conversions
    ├── validator.py            # Connection validation
    ├── card_builder.py         # UI card builder
    └── transport/              # Transport layer (if multi-transport)
        ├── base_transport.py
        ├── <transport>_transport.py
        └── transport_factory.py
```

---

## Step 1: Identifiers

```python
# identifiers.py
from dataclasses import dataclass

@dataclass(frozen=True)
class _Meta:
    name: str
    description: str
    tags: list

class Identifier:
    TYPE = "<name>"   # e.g., "mcp_server", "a2a_client", "rag_client"

META = _Meta(
    name="<Display Name>",
    description="<One-line description>",
    tags=["provider"],
)
```

---

## Step 2: Config

```python
# config.py
from typing import Literal, Optional, List, Dict
from pydantic import HttpUrl
from mas.elements.providers.common.base_config import ProviderBaseConfig
from mas.elements.providers.<name>.identifiers import Identifier

class <Name>ProviderConfig(ProviderBaseConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    # Provider-specific config:
    #   url: HttpUrl
    #   auth_method: Optional[str] = None
    #   bearer_token: Optional[str] = None
    #   timeout: int = 30
```

`ProviderBaseConfig` provides `Config` with `extra = Extra.forbid` and
`arbitrary_types_allowed = True`.

Annotate credential/token fields with `SecretHint` (encrypted at rest, masked in UI).
If a field should stay user-configurable or appear on a card once this provider is
promoted to a built-in resource, see "Field Hints on Config Fields" in `../references/elements.md`
— `providers/mcp_server_client/config.py` is the reference implementation for this.

---

## Step 3: Provider Implementation

Design your provider's public API based on what consuming nodes need:

```python
# <name>_provider.py
from typing import List, Optional

class <Name>Provider:
    def __init__(self, *, url: str, auth: Optional[...] = None, **kwargs):
        # Initialize SDK client / transport
        self._client = <SDKClient>(url=url, ...)

    # Define the public API that nodes will call:
    #   def get_tools(self) -> List[BaseTool]: ...
    #   def query(self, query: str, **params) -> QueryResult: ...
    #   def send_task(self, task: ...) -> TaskResult: ...

    # If provider manages lifecycle:
    #   def connect(self) -> None: ...
    #   def disconnect(self) -> None: ...
    #   def clone(self) -> "<Name>Provider": ...
```

### Architecture patterns from existing providers

**MCP Server Client** — multi-layer:
```
McpProvider (public API: get_tools, refresh_tools)
  ├── McpServerClient (transport + MCP protocol)
  ├── ProviderToolRegistry (cached tool metadata)
  └── creates → McpProxyTool[] (one per discovered tool)
```

**RAG Client** — simple HTTP wrapper:
```
RagProvider (public API: query)
  └── RagClient (httpx HTTP calls to RAG service)
```

**A2A Client** — protocol adapter:
```
A2AProvider (public API: send_task, get_card)
  ├── A2AClient (a2a-sdk protocol client)
  └── A2AConverter (domain ↔ A2A type mapping)
```

### Key rules

- Provider SDK imports are expected (Established Pattern)
- Providers may use `get_async_bridge()` for sync→async bridging
- Providers are injected into nodes via factory kwargs (e.g., `deps.pop("providers")`)
- If multi-transport, create a `transport/` subpackage with a factory

---

## Step 4: Factory

```python
# <name>_factory.py
from typing import Any
from mas.elements.common.base_factory import BaseFactory
from mas.elements.providers.<name>.config import <Name>ProviderConfig
from mas.elements.providers.<name>.<name>_provider import <Name>Provider
from mas.elements.providers.<name>.identifiers import Identifier

class <Name>ProviderFactory(BaseFactory[<Name>ProviderConfig, <Name>Provider]):
    def accepts(self, cfg: <Name>ProviderConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: <Name>ProviderConfig, **kwargs: Any) -> <Name>Provider:
        return <Name>Provider(
            url=str(cfg.url),
            # Map config fields to constructor params
            # If needs auth credentials from ElementDeps:
            #   auth=kwargs.get("auth_credential"),
        )
```

If the provider requires async initialization, add `create_async()`:

```python
    async def create_async(self, cfg, **kwargs) -> <Name>Provider:
        provider = <Name>Provider(...)
        await provider.connect()
        return provider
```

---

## Step 5: Spec

```python
# spec/spec.py
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.providers.<name>.identifiers import Identifier, META
from mas.elements.providers.<name>.config import <Name>ProviderConfig
from mas.elements.providers.<name>.<name>_factory import <Name>ProviderFactory

class <Name>ProviderElementSpec(BaseElementSpec):
    category = ResourceCategory.PROVIDER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = <Name>ProviderConfig
    factory_cls = <Name>ProviderFactory
    tags = META.tags
    # Optional:
    # validator_cls = <Name>ProviderValidator
    # card_builder_cls = <Name>ProviderCardBuilder
```

`spec/__init__.py`:
```python
from mas.elements.providers.<name>.spec.spec import <Name>ProviderElementSpec
```

---

## Step 6: Register in Union Type

Add the config to the `ProviderSpec` discriminated union:

**File:** `lib/mas/elements/providers/types.py`

```python
from mas.elements.providers.<name>.config import <Name>ProviderConfig

ProviderSpec = Annotated[
    Union[
        ...,
        <Name>ProviderConfig,   # ← add here
    ],
    Field(discriminator="type")
]
```

---

## Step 7: Wire into Nodes

Providers are referenced from node configs via `ProviderRef` fields and
resolved at build time by `NodeBuilder`. The node factory receives them as kwargs:

```python
# In the consuming node's factory:
def create(self, cfg, **deps):
    return MyNode(
        providers=deps.pop("providers"),  # List of provider instances
        ...
    )
```

If adding a new provider category that nodes need, update the node's config
to include a `ProviderRef` field and the factory to pop it from deps.

---

## Reference Implementations

| Archetype | Reference | Notes |
|-----------|-----------|-------|
| Multi-transport protocol client | `providers/mcp_server_client/` | MCP protocol, transport factory, tool registry, proxy tool creation |
| Simple HTTP wrapper | `providers/rag_client/` | httpx calls to RAG service API |
| Protocol adapter with converter | `providers/a2a_client/` | A2A SDK, domain ↔ protocol conversion, streaming handlers |

---

## Reviewer Checklist

| Check | Expected |
|-------|----------|
| `spec/__init__.py` exists and exports spec | Auto-discovery depends on it |
| `type: Literal[Identifier.TYPE]` in config | Discriminated union requires it |
| Config added to `ProviderSpec` union in `providers/types.py` | Blueprint deserialization needs it |
| Factory `accepts()` checks `Identifier.TYPE` | Element registry routing |
| Provider is injected into nodes, not instantiated by them | Hex boundary — factories create, nodes consume |

| DO NOT flag | Why |
|-------------|-----|
| SDK imports in provider implementation | Elements ARE the integration layer |
| `get_async_bridge()` usage | Runtime bridge for sync→async — established pattern |
| No `BaseProvider` ABC | Providers have no shared contract — this is intentional |
| Complex transport/client subpackages | Multi-transport providers (MCP) need layered architecture |
