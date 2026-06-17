# Engine & Graph Component

Owns the computational graph: state representation, plan topology, compilation, and execution dispatch.

## Architecture

```
   SESSION
      │ compiles plan → executor
      ▼
  ┌─ENGINE─┐
  │ state   │←──reads/writes── ELEMENTS (nodes declare channels)
  │ plan    │
  │ compile │──delegates──→ ADAPTERS (LangGraph/Temporal executor)
  └─────────┘
      │
      ▼
    CORE (ExecutionContext in StepContext)
```

### Structure

```
lib/mas/graph/
├── state/
│   ├── graph_state.py        GraphState Pydantic model (all channels)
│   ├── state_view.py         Read-only view for nodes
│   └── workspace_state.py    Thread-scoped variable storage
├── plan/
│   ├── graph_plan.py         GraphPlan — abstract topology (nodes + edges)
│   ├── rt_graph_plan.py      RTGraphPlan — topology + bound callables + StepContext
│   └── plan_builder.py       PlanBuilder: blueprint → GraphPlan
├── compilation/
│   ├── graph_builder.py      GraphBuilderFactory, BaseGraphBuilder (ABC)
│   └── engine_graph_executor.py  BaseGraphExecutor (ABC)
└── channels/                 Channel merge logic, metadata
```

### Key Contracts

| Class | Role | Implemented By |
|-------|------|----------------|
| `GraphState` | Shared memory (Pydantic model, annotated channels) | — |
| `GraphPlan` | Logical topology (nodes, edges, entry/exit) | — |
| `RTGraphPlan` | Runtime plan (callables + StepContext bound) | — |
| `BaseGraphBuilder` | Compiles plan → executor (ABC) | `LangGraphBuilder`, `TemporalGraphBuilder` |
| `BaseGraphExecutor` | Runs compiled graph (ABC) | `LangGraphExecutor`, `TemporalGraphExecutor` |
| `WorkspaceState` | Thread-scoped variable storage for delegation | — |

### Plan Layers

```
PlanBuilder.build(spec) → GraphPlan (pure topology)
  → RTGraphPlan (+ callables from SessionRegistry + StepContext)
  → GraphBuilderFactory.create(engine).compile_from_plan(rt_plan)
  → BaseGraphExecutor (engine-specific compiled graph)
```

### Channel Schema (GraphState fields)

Each channel is an `Annotated` field with a merge operator:

| Channel | Type | Merge | External | Streamable |
|---------|------|-------|----------|------------|
| `user_prompt` | `str` | replace | Yes | No |
| `messages` | `List[ChatMessage]` | append | No | Yes |
| `file_attachments` | `List[FileAttachment]` | replace | Yes | No |
| `final_answer` | `Optional[str]` | replace | No | Yes |
| `session_metadata` | `Dict` | merge dicts | No | No |

`external=True` → populated by InputProjector only, never by nodes.

### Channels vs Workspace Variables

| | Channels (GraphState) | Workspace Variables |
|-|----------------------|---------------------|
| Scope | Global (all nodes) | Thread-scoped (delegation chain) |
| Set by | InputProjector (external) or nodes | Nodes via workspace service |
| Persisted | Yes (in SessionRecord) | No |
| Use for | User input, messages, global state | Data following a task through delegation |

## How to Extend

### Adding a New Channel

1. Add annotated field to `lib/mas/graph/state/graph_state.py`
2. Choose merge operator: `operator.add` (append) or `lambda old, new: new` (replace)
3. Set `json_schema_extra`: `external` (if set by InputProjector), `streamable` (if pushed to client)
4. Update element `READS`/`WRITES` ClassVars for nodes that access it
5. If external: populate in `SessionInputProjector.apply()`
6. If streamable: ensure streaming endpoint handles it

## Cross-Component Contracts

### Graph → Elements (State Interface)

Nodes receive state via `run(state: StateView)`:
```python
class StateView:
    def get(self, channel: str) -> Any
    def get_messages(self) -> List[ChatMessage]
```

`ElementValidationService` verifies:
- All channels in element `reads` exist in `GraphState`
- All channels in element `writes` exist in `GraphState`

Rules:
- Nodes MUST NOT write to channels not in their `writes` set
- External channels ONLY populated by InputProjector (never by nodes)

### Graph ← Session (Compilation)

```
PlanBuilder.build(blueprint_spec) → GraphPlan
  → RTGraphPlan(plan, registry, step_contexts)
  → GraphBuilderFactory.create(engine_name).compile_from_plan(rt_plan)
  → BaseGraphExecutor
```

Always recompiled fresh per execution. Initial state = whatever InputProjector staged.

### Graph → Adapters (Engine Implementation)

```
BaseGraphExecutor (abstract, in lib/mas/graph/)
  └── LangGraphExecutor (concrete, in adapters/outbound/langgraph/)
  └── TemporalGraphExecutor (concrete, in adapters/outbound/temporal/)
```

Domain layer NEVER imports adapter code. Adapter implements BaseGraphExecutor interface only.

## Established Patterns

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `GraphBuilderFactory` uses `importlib.import_module()` for lazy engine loading | `lib/mas/engine/factory.py` | Intentional late-binding — the only permitted dynamic import crossing domain → adapters |
| `GraphTraversal` domain class accepts callback functions (not port ABCs) for node execution | `lib/mas/engine/distributed/traversal.py` | BSP algorithm is domain-pure; callbacks injected by Temporal workflow adapter at runtime |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Add/remove channel in GraphState | Element READS/WRITES sets | ValidationService checks alignment |
| Channel merge operator | All nodes writing to that channel | Semantics change (append vs replace) |
| `BaseGraphExecutor` interface | All engine adapters (LangGraph, Temporal) | Contract |
| `StepContext` fields | RTGraphPlan construction in factory | Per-node context |
| Plan builder logic | Blueprint spec format | Input contract |

## Boundaries

**Owns:** graph state schema, topology planning, compilation, execution dispatch, workspace variables.
**Does NOT own:** node implementations (elements), session lifecycle (session), LangGraph/Temporal APIs (adapters).
