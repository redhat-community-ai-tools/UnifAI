---
name: mas-service
scope: Multi-Agent System — orchestration engine for AI agent workflows
parent: ../_index.md
children:
  - session/_index.md
  - elements/_index.md
  - engine-graph/_index.md
  - core/_index.md
  - adapters/_index.md
  - bootstrap/_index.md
when_to_load: Any work touching multi-agent/ directory
---

# Multi-Agent System (MAS)

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

| Path prefix | Load |
|-------------|------|
| `lib/mas/session/` | `session/` |
| `lib/mas/elements/`, `catalog/`, `validation/` | `elements/` |
| `lib/mas/engine/`, `graph/` | `engine-graph/` |
| `lib/mas/core/` | `core/` |
| `adapters/` | `adapters/` |
| `bootstrap/`, `config/` | `bootstrap/` |

## Task Router

| Working on... | Load |
|---------------|------|
| Session lifecycle (create, run, submit, cancel) | `session/_index.md` |
| Nodes, tools, LLMs, providers, retrievers | `elements/_index.md` |
| Graph state channels, compilation, execution | `engine-graph/_index.md` |
| Identity, auth, streaming, enums, ElementDeps | `core/_index.md` |
| Flask endpoints, Mongo repos, new integrations | `adapters/_index.md` |
| Wiring, config, startup | `bootstrap/_index.md` |
| Crossing component boundaries | Both `_index.md` + entering component's `relationships.md` |

## Navigation

```
<component>/
├── _index.md          Graph, contracts, how-to-extend, change impact
└── relationships.md   Deep cross-boundary implementation details (load only when needed)
```

1. Identify component from routing table
2. Load `<component>/_index.md`
3. If crossing boundaries → load target's `relationships.md`
4. Before writing code → load `rules.md` + `../architecture/standards.md`
