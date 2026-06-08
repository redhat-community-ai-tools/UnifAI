---
name: session-relationships
scope: Deep implementation details for crossing session boundaries
parent: _index.md
when_to_load: Actively implementing a feature that crosses from session into elements or engine
---

# Session → Elements (Building)

## Injection Chain

```
container.py → WorkflowSessionFactory(element_registry, engine_name, auth_service, file_retrieve_tool_factory)
  → factory.build_session(record, spec)
    → ElementDeps(execution_ctx=holder, auth_service, file_retrieve_tool_factory)
    → SessionElementBuilder.build(spec, deps) → SessionRegistry
```

## Build Order (Topological)

Auth → Provider → LLM → Retriever → Condition → Tool → Node

Determined by `BaseElementSpec.dependencies` ClassVar.

## Invariants

- Elements NEVER import session code
- Session NEVER imports specific element implementations
- ElementDeps is the ONLY injection pathway (see `core/_index.md`)
- Elements built ONCE per session run

---

# Session → Engine (Execution)

## The Handoff

```
WorkflowSessionFactory.build_session()
  → RTGraphPlan → GraphBuilderFactory.create(engine).compile_from_plan() → BaseGraphExecutor

ForegroundSessionRunner.run():
  lifecycle.begin(record, scope)     # status → RUNNING
  final_state = session.executable_graph.run(graph_state, session_id=...)
  lifecycle.complete(record, state)  # status → COMPLETED
```

## What Crosses the Boundary

| Session → Engine | Engine → Session |
|-----------------|-----------------|
| Initial GraphState (post-staging) | Final GraphState (return value) |
| Compiled BaseGraphExecutor | Exceptions on failure |
| session_id as kwarg | — |

## Invariants

- Engine NEVER modifies SessionRecord
- Engine NEVER manages status transitions
- Session NEVER knows about LangGraph/Temporal APIs
- Always recompile from plan (no executor reuse)
