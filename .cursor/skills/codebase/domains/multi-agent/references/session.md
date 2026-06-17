# Session Component

Owns the full lifecycle of a user interaction: creation → staging → hydration → execution → completion.

## Architecture

```
 BOOTSTRAP ──wires──→ SESSION
                        │
          ┌─────────────┼──────────────┐
          ▼             ▼              ▼
     ELEMENTS       ENGINE         CORE
  (builds specs)  (compiles+runs) (identity, context)
          │             │
          ▼             ▼
      ADAPTERS      ADAPTERS
  (Gemini upload) (LangGraph/Temporal)
```

### Structure

```
lib/mas/session/
├── service.py                  Public facade (create, run, submit, cancel)
├── domain/
│   ├── session_record.py       Persistable state (no live objects)
│   ├── workflow_session.py     Runtime: record + registry + graph + executor
│   ├── status.py               SessionStatus enum
│   └── exceptions.py
├── management/
│   └── user_session_manager.py CRUD, hydration, listing
├── building/
│   └── workflow_session_factory.py  Blueprint → WorkflowSession
├── execution/
│   ├── ports.py                BackgroundSessionEngine, IFileUploadService
│   ├── input_projector.py      STAGE phase (inputs → persisted state)
│   ├── lifecycle.py            Status transitions (begin/complete/fail/cancel)
│   └── foreground_runner.py    In-process execution
└── repository/
    └── repository.py           SessionRepository port (ABC)
```

### Key Contracts

| Class | Role | Implemented By |
|-------|------|----------------|
| `SessionService` | Public API facade | — |
| `SessionRepository` | Persistence port | `MongoSessionRepository` |
| `BackgroundSessionEngine` | Async execution port | `TemporalSessionEngine` |
| `IFileUploadService` | File upload port | `GeminiFileUploadAdapter` |
| `SessionInputProjector` | Stages inputs into record | — |
| `WorkflowSessionFactory` | Hydrates record → runtime session | — |
| `SessionLifecycle` | Status transitions | — |

### Two-Phase Invariant

```
STAGE:   InputProjector.apply(record, inputs, files) → persist → QUEUED
EXECUTE: manager.get_session(id) → hydrate → runner.run() → COMPLETED|FAILED
```

Never combined. Staging persists BEFORE execution starts.

## How to Extend

### Adding a New Execution Port

1. Define ABC in `execution/ports.py` with `@abstractmethod`
2. Create adapter in `adapters/outbound/<technology>/<concept>_adapter.py`
3. Add config to `config/app_config.py` (empty string = disabled)
4. Wire in `bootstrap/container.py` (conditional on config)
5. Inject into `SessionInputProjector` or `SessionService` via constructor
6. Service handles `None` gracefully when feature disabled

## Cross-Component Contracts

### Session → Elements (Building)

Injection chain:
```
container.py → WorkflowSessionFactory(element_registry, engine_name, auth_service, file_retrieve_tool_factory)
  → factory.build_session(record, spec)
    → ElementDeps(execution_ctx=holder, auth_service, file_retrieve_tool_factory)
    → SessionElementBuilder.build(spec, deps) → SessionRegistry
```

Build order (topological): Auth → Provider → LLM → Retriever → Condition → Tool → Node

Invariants:
- Elements NEVER import session code
- Session NEVER imports specific element implementations
- ElementDeps is the ONLY injection pathway (see `references/core.md`)
- Elements built ONCE per session run

### Session → Engine (Execution)

```
WorkflowSessionFactory.build_session()
  → RTGraphPlan → GraphBuilderFactory.create(engine).compile_from_plan() → BaseGraphExecutor

ForegroundSessionRunner.run():
  lifecycle.begin(record, scope)     # status → RUNNING
  final_state = session.executable_graph.run(graph_state, session_id=...)
  lifecycle.complete(record, state)  # status → COMPLETED
```

| Session → Engine | Engine → Session |
|-----------------|-----------------|
| Initial GraphState (post-staging) | Final GraphState (return value) |
| Compiled BaseGraphExecutor | Exceptions on failure |
| session_id as kwarg | — |

### Machine-Checkable Invariants

| ID | Rule | Violating Import Pattern | Severity |
|----|------|--------------------------|----------|
| INV-S01 | Elements never import session | `from mas.session` in `lib/mas/elements/**` | CRITICAL |
| INV-S02 | Session never imports specific elements | `from mas.elements.nodes.` or `from mas.elements.tools.` in `lib/mas/session/**` | CRITICAL |
| INV-S03 | Session never knows about LangGraph | `from langgraph` in `lib/mas/session/**` | CRITICAL |
| INV-S04 | Session never knows about Temporal APIs | `from temporalio` in `lib/mas/session/**` | CRITICAL |
| INV-S05 | Engine never modifies SessionRecord | `SessionRecord` + any `.save()`/`.update()` in `lib/mas/engine/**` | CRITICAL |
| INV-S06 | Engine never manages status transitions | `SessionStatus` assignment in `lib/mas/engine/**` | CRITICAL |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| `SessionStatus` enum | `SessionLifecycle`, streaming endpoint, repo queries | Status machine |
| `InputProjector.apply()` signature | `SessionService._stage()`, Flask endpoint | Call chain |
| `WorkflowSessionFactory` constructor | `container.py` wiring | Injection |
| Add field to `SessionRecord` | Mongo serialization in adapter | Persistence |
| File upload limits | `config/app_config.py` + `container.py` | Config source |

## Boundaries

**Owns:** record persistence, status transitions, input staging, hydration, execution orchestration.
**Does NOT own:** graph execution logic (engine), element instantiation (elements), streaming protocols (core).
