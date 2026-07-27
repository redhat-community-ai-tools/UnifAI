---
name: add-new-tool
scope: Step-by-step recipe for adding a new tool to MAS
parent: ../SKILL.md
when_to_load: Creating a new tool element under lib/mas/elements/tools/
---

# Add a New Tool

## Package Structure

Create the following tree under `lib/mas/elements/tools/<name>/`:

```
<name>/
├── identifiers.py              # TYPE constant + META dataclass
├── config.py                   # Pydantic config model
├── <name>.py                   # BaseTool implementation
├── <name>_factory.py           # BaseFactory subclass
├── spec/
│   ├── __init__.py             # re-exports the spec class
│   └── spec.py                 # BaseElementSpec subclass
└── (optional)
    ├── models.py               # args schema + response models
    └── validator.py            # connection validation
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
    TYPE = "<name>"   # unique across all elements

META = _Meta(
    name="<Display Name>",
    description="<One-line description>",
    tags=["tool"],
)
```

---

## Step 2: Config

```python
# config.py
from typing import Literal
from pydantic import BaseModel
from mas.elements.tools.<name>.identifiers import Identifier

class <Name>ToolConfig(BaseModel):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    # Tool-specific configuration:
    #   endpoint: str = ""
    #   timeout: int = 30
```

If a field should stay user-configurable or appear on a card once this tool is promoted
to a built-in resource, annotate it with `ReadOnlyHint`/`CardHint`/`SecretHint` — see
"Field Hints on Config Fields" in `../references/elements.md`. (Builtin tools under
`tools/builtin/` are injected by nodes, not element-registry items, so this does not apply to them.)

---

## Step 3: Args Schema

Define the tool's input arguments as a Pydantic model:

```python
# models.py (or inline in the tool file)
from pydantic import BaseModel, Field

class <Name>Args(BaseModel):
    query: str = Field(..., description="The search query")
    max_results: int = Field(5, description="Maximum results to return")
```

This schema is used by `to_definition()` to generate the JSON Schema that LLMs see.
Each field's `description` becomes the parameter description in the tool definition.

### Alternative: Raw JSON Schema dict

For dynamically-defined tools (e.g., MCP proxy), set `args_schema` to a dict:

```python
self.args_schema = {"type": "object", "properties": {...}, "required": [...]}
```

`get_args_schema_json()` handles both `Type[BaseModel]` and `dict` forms.

---

## Step 4: Tool Implementation

```python
# <name>.py
from typing import Any, Optional, Type
from pydantic import BaseModel
from mas.elements.tools.common.base_tool import BaseTool

class <Name>Tool(BaseTool):
    name: str = "<tool_name>"
    description: str = "<Description the LLM sees when deciding to use this tool>"
    args_schema: Optional[Type[BaseModel]] = <Name>Args

    def __init__(self, **kwargs):
        super().__init__()
        # Store config dependencies

    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool. Arguments match args_schema fields."""
        # kwargs contains the fields from args_schema
        # Return a string or serializable result
        return result
```

### BaseTool contract

```python
class BaseTool(ABC):
    name: str                                    # tool identifier
    description: str                             # LLM-facing description
    args_schema: Optional[Type[BaseModel]] = None  # or dict

    @abstractmethod
    def run(self, *args, **kwargs) -> Any: ...   # MUST implement

    async def arun(self, *args, **kwargs) -> Any:  # default: run in thread
        return await asyncio.to_thread(self.run, *args, **kwargs)

    def to_definition(self) -> ToolDefinition:     # auto-generated
        # Builds ToolDefinition from name, description, args_schema

    def get_args_schema_json(self) -> Optional[Dict[str, Any]]:
        # Returns JSON Schema from args_schema (Pydantic model or dict)
```

### Key rules

- `run()` is the only abstract method — always implement it
- `arun()` has a default (thread pool) — override only if you have a native async implementation
- `to_definition()` is auto-generated — do NOT override unless you need custom schema manipulation
- Tool `name` should be a short, LLM-friendly identifier (snake_case)
- Tool `description` should clearly explain what the tool does, when to use it, and what it returns

---

## Step 5: Factory

```python
# <name>_factory.py
from mas.elements.common.base_factory import BaseFactory
from mas.elements.tools.<name>.config import <Name>ToolConfig
from mas.elements.tools.<name>.<name> import <Name>Tool
from mas.elements.tools.<name>.identifiers import Identifier

class <Name>ToolFactory(BaseFactory[<Name>ToolConfig, <Name>Tool]):
    def accepts(self, cfg: <Name>ToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: <Name>ToolConfig, **deps) -> <Name>Tool:
        return <Name>Tool(
            # Pass config fields as needed
        )
```

---

## Step 6: Spec

```python
# spec/spec.py
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.tools.<name>.identifiers import Identifier, META
from mas.elements.tools.<name>.config import <Name>ToolConfig
from mas.elements.tools.<name>.<name>_factory import <Name>ToolFactory

class <Name>ToolElementSpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = <Name>ToolConfig
    factory_cls = <Name>ToolFactory
    tags = META.tags
    # Optional:
    # validator_cls = <Name>Validator
```

`spec/__init__.py`:
```python
from mas.elements.tools.<name>.spec.spec import <Name>ToolElementSpec
```

---

## Step 7: Register in Union Type

Add the config to the `ToolsSpec` discriminated union:

**File:** `lib/mas/elements/tools/types.py`

```python
from mas.elements.tools.<name>.config import <Name>ToolConfig

ToolsSpec = Annotated[
    Union[
        ...,
        <Name>ToolConfig,   # ← add here
    ],
    Field(discriminator="type")
]
```

---

## Builtin Tools (Alternative Path)

Builtin tools are injected by nodes (not configured in blueprints). Different pattern:

1. Create module in `elements/tools/builtin/<name>/`
2. Implement `BaseTool` subclass
3. Inject in target node's `_create_builtin_tools()` or equivalent
4. If needs infrastructure: add factory callable to `ElementDeps` (see `references/core.md`)
5. No spec/factory/config needed — builtins are not element-registry items

Reference: `tools/builtin/delegation/delegate_task.py`, `tools/builtin/retriever/`.

---

## Reference Implementations

| Archetype | Reference | Notes |
|-----------|-----------|-------|
| Simple external API tool | `tools/web_fetch/` | HTTP fetch, Pydantic args schema |
| SSH/shell execution | `tools/ssh_exec/` | Paramiko SDK, connection validation |
| Provider-backed proxy | `tools/mcp_proxy/` | Dynamic args from MCP, factory creates from provider |
| Builtin (injected, no spec) | `tools/builtin/delegation/` | `DelegateTaskTool` — not in registry |

---

## Reviewer Checklist

| Check | Expected |
|-------|----------|
| `spec/__init__.py` exists and exports spec | Auto-discovery depends on it |
| `type: Literal[Identifier.TYPE]` in config | Discriminated union requires it |
| Config added to `ToolsSpec` union in `tools/types.py` | Blueprint deserialization needs it |
| `run()` implemented | Only abstract method on `BaseTool` |
| `name` and `description` are LLM-friendly | LLM sees these when deciding tool use |
| `args_schema` fields have `description` | LLM needs field descriptions for correct usage |

| DO NOT flag | Why |
|-------------|-----|
| SDK imports in tool implementations | Elements ARE the integration layer |
| `args_schema` as raw dict (not Pydantic model) | Supported for dynamic tools like MCP proxy |
