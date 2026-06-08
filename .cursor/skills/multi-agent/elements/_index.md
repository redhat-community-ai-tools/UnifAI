---
name: mas-elements
scope: Element plugin system — nodes, tools, LLMs, providers, retrievers, conditions, auths
parent: ../_index.md
when_to_load: Adding or modifying any element type, catalog discovery, or element validation
---

# Elements & Catalog

Plugin system providing all agent capabilities. Self-describing packages, auto-discovered at startup.

## Dependency Graph

```
    SESSION
       │ builds via ElementDeps (see core/)
       ▼
  ┌─ELEMENTS─┐
  │  nodes    │──reads/writes──→ ENGINE (GraphState channels)
  │  tools    │
  │  llms     │──uses──→ CORE (enums, identity, auth)
  │  providers│
  └───────────┘
       │ implements ports from
       ▼
   ADAPTERS (Gemini retrieve, MCP proxy, OAuth)
```

## Structure

```
lib/mas/elements/
├── common/                  BaseElementSpec, BaseFactory, ElementValidator
├── nodes/
│   ├── custom_agent/        General-purpose agent (LLM + tools)
│   ├── orchestrator/        Multi-agent coordinator + work plans
│   ├── user_question/       Entry node (receives user input)
│   ├── final_answer/        Exit node
│   └── ...                  deep_agent, a2a_agent, branch_chooser, llm_merger
├── llms/common/chat/        ChatMessage, FileAttachment, Role models
├── tools/builtin/           Auto-injected tools (delegation, retriever, time, file_retrieve)
├── tools/mcp_proxy/         MCP server tool proxy
├── providers/               rag_client, mcp_server_client, a2a_client
├── retrievers/              docs_rag, slack
├── conditions/              router_boolean, router_direct, threshold
└── auths/                   oauth_client, github_oauth, google_oauth

lib/mas/catalog/             ElementRegistry, SpecDiscoverer, CatalogService
lib/mas/validation/          ElementValidationService
```

## Key Contracts

| Class | Role |
|-------|------|
| `BaseElementSpec` | Self-describing element declaration (ClassVars: category, type_key, config_schema, factory_cls) |
| `BaseFactory` | Creates element instances from config + ElementDeps kwargs |
| `ElementRegistry` | Holds all discovered specs, queried by category/type_key |
| `BaseNode` | Node base class (READS/WRITES channel sets, run(state)) |
| `ChatMessage` | Shared message model (role, content, file_attachments, tool_calls) |
| `FileAttachment` | Frozen Pydantic model (file_name, mime_type, file_uri, size_bytes) |

## Element Spec Required ClassVars

| Field | Type | Purpose |
|-------|------|---------|
| `category` | `ResourceCategory` | NODE, TOOL, LLM, etc. |
| `type_key` | `str` | Unique identifier |
| `config_schema` | `Type[BaseModel]` | Pydantic config model |
| `factory_cls` | `Type[BaseFactory]` | Instance creator |
| `reads` | `Set[Channel]` | GraphState channels consumed |
| `writes` | `Set[Channel]` | GraphState channels produced |

## How to Add a New Element

1. Create package: `elements/<category>/<name>/`
2. Create `identifiers.py` with type_key constant
3. Create `config.py` — Pydantic BaseModel for element configuration
4. Create `<name>_factory.py` — BaseFactory subclass with `create()` method
5. Create `spec/spec.py` — BaseElementSpec subclass with all ClassVars set
6. Auto-discovered at startup — no registration needed

## How to Add a New Builtin Tool

1. Create module in `elements/tools/builtin/<name>/`
2. Implement tool class extending `BaseTool`
3. Inject in target node's `_create_builtin_tools()` method
4. If needs infrastructure: add factory callable to `ElementDeps` (see `core/_index.md`)

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Element spec ClassVars | `__init_subclass__` enforces at definition time | Compile-time check |
| `BaseNode.READS/WRITES` | GraphState must have those channels | Validation service checks |
| `ChatMessage` fields | Serialization in repos + streaming | Crosses persistence boundary |
| `FileAttachment` model | InputProjector, orchestrator context, delegate_task | Used across delegation chain |
| Add to `ElementDeps` | `core/element_deps.py` + `container.py` + factory | Injection chain (see `core/_index.md`) |

## Data Flow: Files Through Elements

```
InputProjector → GraphState.file_attachments (channel)
  → UserQuestionNode → workspace variable
  → OrchestratorNode → reads workspace → context
  → DelegateTaskTool → propagates workspace to child
  → CustomAgentNode → reads workspace → injects retrieve tool + facts
```

## Boundaries

**Owns:** all agent capabilities, LLM integrations, tool implementations, node execution, catalog discovery.
**Does NOT own:** graph state schema (engine), session lifecycle (session), infrastructure adapters (adapters).
