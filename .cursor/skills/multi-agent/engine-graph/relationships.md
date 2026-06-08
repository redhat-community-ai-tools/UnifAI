---
name: engine-graph-relationships
scope: Deep implementation details for graph crossing into elements and adapters
parent: _index.md
when_to_load: Implementing features touching state channels used by elements, or engine adapter work
---

# Graph → Elements (State Interface)

## How Nodes Access State

Nodes receive state via `run(state: StateView)`:
```python
class StateView:
    def get(self, channel: str) -> Any
    def get_messages(self) -> List[ChatMessage]
```

## Validation Contract

`ElementValidationService` verifies:
- All channels in element `reads` exist in `GraphState`
- All channels in element `writes` exist in `GraphState`
- Missing channels → build-time validation error

## Rules

- Nodes MUST NOT write to channels not in their `writes` set
- External channels ONLY populated by InputProjector (never by nodes)
- Merge operators define conflict resolution — consider when adding channels

---

# Graph ← Session (Compilation)

## Full Compilation Path

```
PlanBuilder.build(blueprint_spec) → GraphPlan
  → RTGraphPlan(plan, registry, step_contexts)
  → GraphBuilderFactory.create(engine_name).compile_from_plan(rt_plan)
  → BaseGraphExecutor
```

Always recompiled fresh per execution. Initial state = whatever InputProjector staged.

---

# Graph → Adapters (Engine Implementation)

```
BaseGraphExecutor (abstract, in lib/mas/graph/)
  └── LangGraphExecutor (concrete, in adapters/outbound/langgraph/)
  └── TemporalGraphExecutor (concrete, in adapters/outbound/temporal/)
```

## Rules

- Domain layer NEVER imports adapter code
- Adapter implements BaseGraphExecutor interface only
- All engine-specific config stays in adapter (thread_id, checkpointer, etc.)
