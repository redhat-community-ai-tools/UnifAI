---
name: add-new-node
scope: Step-by-step recipe for adding a new agent node to MAS
parent: ../SKILL.md
when_to_load: Creating a new node element under lib/mas/elements/nodes/
---

# Add a New Node

## Package Structure

Create the following tree under `lib/mas/elements/nodes/<name>/`:

```
<name>/
├── identifiers.py              # TYPE constant + META dataclass
├── config.py                   # Pydantic config model
├── <name>_factory.py           # BaseFactory subclass
├── <name>_node.py              # BaseNode subclass (runtime)
├── spec/
│   ├── __init__.py             # re-exports the spec class
│   └── spec.py                 # BaseElementSpec subclass
└── (optional)
    ├── validator.py            # ElementValidator subclass
    └── card_builder.py         # CardBuilder subclass
```

`spec/__init__.py` MUST exist and export the spec — `SpecDiscoverer` imports it.

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
    TYPE = "<name>_node"   # unique across all elements

META = _Meta(
    name="<Display Name>",
    description="<One-line description>",
    tags=["<category>"],
)
```

---

## Step 2: Config

```python
# config.py
from typing import Literal
from mas.elements.nodes.common.node_base_config import NodeBaseConfig
from mas.elements.nodes.<name>.identifiers import Identifier

class <Name>NodeConfig(NodeBaseConfig):
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    # Add fields. Use Ref types for element dependencies:
    #   llm: LLMRef           → resolved to BaseLLM at build time
    #   tools: List[ToolRef]  → resolved to List[BaseTool]
    #   retriever: Optional[RetrieverRef] = None
    #   providers: List[ProviderRef] = []
```

`NodeBaseConfig` provides common fields like `retries`. The `type` field
is the discriminator for the `NodeSpec` union — use `Literal[Identifier.TYPE]`.

---

## Step 3: Choose Mixins

Select mixin stack based on your node's execution model:

### Internal LLM loop (node runs its own ReAct/plan-execute)

Follow `CustomAgentNode`:

```python
class <Name>Node(
    WorkloadCapableMixin,     # threads, workspaces
    IEMCapableMixin,          # inter-element messaging
    AgentCapableMixin,        # agent loop (requires LlmCapableMixin)
    LlmCapableMixin,          # chat(), stream(), bind_tools()
    RetrieverCapableMixin,    # optional RAG augmentation
    BaseNode,                 # MUST be last
):
```

### External engine delegation (node delegates to remote/external agent)

Follow `A2AAgentNode`, `DeepAgentNode`, `ClaudeAgentNode`:

```python
class <Name>Node(
    WorkloadCapableMixin,
    IEMCapableMixin,
    RetrieverCapableMixin,
    BaseNode,
):
```

No `LlmCapableMixin` / `AgentCapableMixin` — the LLM loop is not yours.
Emit streaming events manually: `self._stream({"type": "llm_token", "chunk": ...})`.

### Simple logic (no LLM, no IEM)

Follow `BranchChooserNode`:

```python
class <Name>Node(BaseNode):
```

### Mixin reference

| Mixin | Adds channels | Provides | Requires |
|-------|---------------|----------|----------|
| `LlmCapableMixin` | — | `chat(messages, tools)`, `bind_tools()`, streaming token emission | `__init__(llm: BaseLLM, system_message: str)` |
| `AgentCapableMixin` | — | `run_agent()`, `stream_agent()`, strategy/iterator creation | `chat`, `_stream`, `is_streaming` in MRO |
| `IEMCapableMixin` | `inter_packets` | `process_packets()`, `send_task()`, `broadcast_task()`, `reply_task()` | `SupportsStateContext` |
| `WorkloadCapableMixin` | `threads`, `workspaces`, `task_threads` | `threads`, `workspaces` properties, workspace helpers | — |
| `RetrieverCapableMixin` | — | `_retrieve(query)`, `augment_with_context(msg)` | `__init__(retriever=None)` |
| `StreamingCapableMixin` | — | `_stream(payload)`, `is_streaming()` | (inherited via `BaseNode`) |

---

## Step 4: Implement the Node

```python
# <name>_node.py
from typing import ClassVar
from mas.elements.nodes.common.base_node import BaseNode
from mas.graph.state.state_view import StateView

class <Name>Node(
    # ... mixin stack ...
    BaseNode,
):
    READS: ClassVar[set[str]] = set()   # add Channel values if reading extra channels
    WRITES: ClassVar[set[str]] = set()  # add Channel values if writing extra channels

    def __init__(self, *, <deps from factory>, **kwargs):
        super().__init__(**kwargs)
        # store deps

    def run(self, state: StateView) -> StateView:
        # For IEM-capable nodes:
        self.process_packets(state)
        return state

    # For IEM-capable agent nodes, override:
    def handle_task_packet(self, packet) -> None:
        task = packet.extract_task()
        task.mark_processed(self.uid)
        # 1. Build context
        # 2. Execute (LLM / delegation)
        # 3. Create AgentResult
        # 4. Route response
```

### Channel declarations

Channels are string values from the `Channel` enum. Mixins contribute their own
via `MIXIN_READS`/`MIXIN_WRITES` — you only need to set `READS`/`WRITES` for
channels beyond what your mixins already declare.

The spec derives channels from the node class:
```python
reads = <Name>Node.total_reads()
writes = <Name>Node.total_writes()
```

### IEM response routing pattern

Agent nodes implement `_route_response()` locally (not in a mixin).
Copy the established pattern from `CustomAgentNode`:

```python
def _route_response(self, task: Task, agent_result: AgentResult, original_packet) -> None:
    if not task.should_respond:
        self._execute_normal_broadcast(task, agent_result)
    elif task.response_to in self._get_adjacent_nodes_uids():
        self._execute_direct_response(task, agent_result, original_packet)
    else:
        self._execute_broadcast_with_response(task, agent_result)
```

This pattern is duplicated across four agent nodes — see Established Patterns
in `references/elements.md`.

---

## Step 5: Factory

```python
# <name>_factory.py
from mas.elements.common.base_factory import BaseFactory
from mas.elements.nodes.<name>.config import <Name>NodeConfig
from mas.elements.nodes.<name>.<name>_node import <Name>Node
from mas.elements.nodes.<name>.identifiers import Identifier

class <Name>NodeFactory(BaseFactory[<Name>NodeConfig, <Name>Node]):
    def accepts(self, cfg: <Name>NodeConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(self, cfg: <Name>NodeConfig, **deps) -> <Name>Node:
        return <Name>Node(
            # Pop resolved Ref deps:
            #   llm=deps.pop("llm"),
            #   tools=deps.pop("tools"),
            #   retriever=deps.pop("retriever"),
            #   mcp_providers=deps.pop("providers"),
            # Pass config fields:
            #   system_message=cfg.system_message,
            # Pass remaining deps (includes deps=ElementDeps):
            **deps,
        )
```

`Ref` fields in the config are auto-resolved by `NodeBuilder` before `create()` is called.
They arrive as keyword arguments matching the config field name.

---

## Step 6: Spec

```python
# spec/spec.py
from mas.elements.common.base_element_spec import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.nodes.<name>.identifiers import Identifier, META
from mas.elements.nodes.<name>.config import <Name>NodeConfig
from mas.elements.nodes.<name>.<name>_factory import <Name>NodeFactory
from mas.elements.nodes.<name>.<name>_node import <Name>Node

class <Name>NodeElementSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = <Name>NodeConfig
    factory_cls = <Name>NodeFactory
    reads = <Name>Node.total_reads()
    writes = <Name>Node.total_writes()
    tags = META.tags
    # Optional:
    # validator_cls = <Name>Validator
    # card_builder_cls = <Name>CardBuilder
```

`spec/__init__.py`:
```python
from mas.elements.nodes.<name>.spec.spec import <Name>NodeElementSpec
```

---

## Step 7: Register in Union Type

Add the config to the `NodeSpec` discriminated union:

**File:** `lib/mas/elements/nodes/types.py`

```python
from mas.elements.nodes.<name>.config import <Name>NodeConfig

NodeSpec = Annotated[
    Union[
        ...,
        <Name>NodeConfig,   # ← add here
    ],
    Field(discriminator="type")
]
```

---

## Streaming Events

| Event type | When to emit | Payload |
|------------|--------------|---------|
| `llm_token` | During LLM generation | `{"type": "llm_token", "chunk": "<text>"}` |
| `tool_calling` | When agent invokes a tool | `{"type": "tool_calling", "tool": "<name>", "call_id": "<id>", "args": {...}}` |
| `complete` | End of node execution | Auto-emitted by `BaseNode.__call__` |
| `field_update` | State field changed | Via `self._stream_field(field_name, value)` |

For internal-LLM nodes, streaming is automatic via `LlmCapableMixin`.
For delegation nodes, emit manually: `self._stream({"type": "llm_token", "chunk": chunk})`.
Guard manual emissions: `if self.is_streaming():`.

---

## Reference Implementations

| Archetype | Reference | When to follow |
|-----------|-----------|----------------|
| Tool-using agent (internal LLM loop) | `nodes/custom_agent/` | Node runs its own ReAct/plan-execute loop with tools |
| Multi-agent orchestrator | `nodes/orchestrator/` | Node coordinates other nodes via work plans |
| Remote agent delegation (A2A) | `nodes/a2a_agent/` | Delegates to external agent via A2A protocol |
| External engine with workspace I/O | `nodes/deep_agent/` | Delegates + sets up local workspace/shell |
| External SDK delegation | `nodes/claude_agent/` | Delegates to Claude agent SDK |
| Simple merge (internal LLM, no agent loop) | `nodes/llm_merger/` | LLM-powered merge without full agent capabilities |
| Workflow entry point | `nodes/user_question/` | Receives user input, no LLM |
| Workflow exit point | `nodes/final_answer/` | Aggregates results, no LLM |
| Test stub | `nodes/mock_agent/` | Echo node for testing |

---

## Reviewer Checklist

| Check | Expected |
|-------|----------|
| `spec/__init__.py` exists and exports spec | Auto-discovery depends on it |
| `type: Literal[Identifier.TYPE]` in config | Discriminated union requires it |
| Config added to `NodeSpec` union in `nodes/types.py` | Blueprint deserialization needs it |
| `BaseNode` is last in MRO | Mixin channel aggregation depends on MRO order |
| `run()` returns `StateView` | Contract with graph executor |
| Factory `accepts()` checks `Identifier.TYPE` | Element registry routing |
| No direct adapter/infrastructure imports in node | Unless delegation-style (see below) |

| DO NOT flag | Why |
|-------------|-----|
| SDK imports in delegation-style nodes | Established pattern — see `references/elements.md` |
| Direct I/O (`os.makedirs`, `tempfile`) in external-engine nodes | Session workspace is owned by the element at runtime |
| Skipping `LlmCapableMixin` for delegation nodes | External engine handles the LLM loop |
| Duplicate `_route_response` / `_build_conversation_context` | Established pattern — extract to mixin is optional |
| `get_async_bridge()` calls | Runtime bridge for sync nodes calling async SDKs |
