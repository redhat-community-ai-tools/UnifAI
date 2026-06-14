---
name: mas-knowledge
description: >-
  Hierarchical knowledge system for the Multi-Agent System (MAS).
  Provides architectural navigation, component deep-dives, cross-component
  relationship contracts, and MAS-specific rules. Use when working on any
  file under multi-agent/ — start by reading _index.md to identify which
  component and relationship skills to load.
---

# MAS Knowledge System

## How to Use

1. **Read `_index.md`** — identify which component(s) your task involves
2. **Load component directory** — read `<component>/_index.md` for architecture and patterns
3. **If crossing components** — read `<component>/relationships.md` for contracts and flow
4. **Before writing code** — read `rules.md` for MAS-specific enforcement
5. **Always** — load `../../architecture/standards.md` for universal rules (SOLID, Pydantic, etc.)

## Structure

```
multi-agent/
├── SKILL.md                Cursor discovery metadata (this file)
├── _index.md               Navigation, routing table, service map
├── rules.md                MAS-specific architectural rules (10 rules)
├── recipes/
│   ├── add-new-node.md     Full recipe: package, mixins, IEM, streaming, reviewer checklist
│   ├── add-new-llm.md      Full recipe: BaseLLM, converters, streaming, bind_tools
│   ├── add-new-tool.md     Full recipe: BaseTool, args_schema, builtin vs registered
│   └── add-new-provider.md Full recipe: provider pattern, no BaseProvider, transport layers
├── session/
│   ├── _index.md           Session lifecycle, two-phase execution, ports, boundaries
│   └── relationships.md    → elements (building), → engine (execution), → core (context)
├── elements/
│   ├── _index.md           Plugin system, nodes, tools, LLMs, auto-discovery
│   └── relationships.md    → graph (channels), ← session (deps injection), → core (models)
├── engine-graph/
│   ├── _index.md           GraphState channels, plan layers, compilation, executors
│   └── relationships.md    → elements (state interface), ← session (compilation), → adapters
├── core/
│   ├── _index.md           Identity, ExecutionContext, ElementDeps, channels, enums
│   └── relationships.md    → all (identity flow), → session (context), → elements (deps)
├── adapters/
│   ├── _index.md           Inbound/outbound structure, conventions, adding new integrations
│   └── relationships.md    ← domain (ports), ← bootstrap (wiring), → external systems
└── bootstrap/
    └── _index.md           Composition root, config patterns, wiring conventions
```

## Companion Skills

```
architecture/
├── SKILL.md                Discovery metadata
└── standards.md            Universal rules: SOLID, hexagonal, Pydantic, enums, types, imports
```

## Each Component is Self-Contained

Every component directory includes:
- **`_index.md`** — architecture, structure, ports, public API, boundaries
- **`relationships.md`** — how it connects to other components, contracts, data flow, rules
