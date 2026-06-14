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

See full recipes in `../recipes/` for detailed step-by-step guides with exact
contracts, reference implementations, and reviewer checklists:

| Element type | Recipe | Reference impl |
|-------------|--------|----------------|
| Node | `../recipes/add-new-node.md` | `nodes/custom_agent/` (LLM), `nodes/a2a_agent/` (delegation) |
| LLM | `../recipes/add-new-llm.md` | `llms/openai/`, `llms/google_genai/` |
| Tool | `../recipes/add-new-tool.md` | `tools/web_fetch/`, `tools/mcp_proxy/` |
| Provider | `../recipes/add-new-provider.md` | `providers/mcp_server_client/` |

Quick checklist (all element types):
1. Create package: `elements/<category>/<name>/`
2. Create `identifiers.py` with type_key constant
3. Create `config.py` — Pydantic config with `type: Literal[Identifier.TYPE]`
4. Create implementation — extend the category's base class
5. Create `<name>_factory.py` — `BaseFactory` subclass with `create()` method
6. Create `spec/spec.py` — `BaseElementSpec` subclass with all ClassVars set
7. Add config to the category's `types.py` union type
8. Auto-discovered at startup — no manual registration needed

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

## Established Patterns — Elements Plugin Layer

The elements layer wraps external SDKs behind domain abstractions.
These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Framework SDK imports (`openai`, `google.genai`, `a2a`, `claude_agent_sdk`, `deepagents`, `langchain_core`, `mcp`, `paramiko`, `safehttpx`) | All LLM, tool, provider, and node implementations | Elements ARE the integration layer — SDK coupling is their job |
| Direct I/O in nodes (`os.makedirs`, `tempfile.mkdtemp`, `shutil.rmtree`, `subprocess.run`) | `DeepAgentNode`, `ClaudeAgentNode` | Session workspace setup and skills-clone are owned by the external-engine node at runtime |
| Skipping `LlmCapableMixin` / `AgentCapableMixin` for delegation-style nodes | `A2AAgentNode`, `ClaudeAgentNode`, `DeepAgentNode` | These nodes delegate to an external execution engine; the LLM loop is not theirs |
| LangChain type imports (`BaseMessage`, `AIMessage`, `StructuredTool`, `BaseChatModel`) | `llms/common/`, `tools/common/converter.py`, `deep_agent_node.py` | LangChain is a first-class integration target; converter modules handle the boundary |
| Duplicate IEM routing logic (`_route_response`, `_get_adjacent_nodes_uids`, `_execute_direct_response`) | `CustomAgentNode`, `A2AAgentNode`, `ClaudeAgentNode`, `DeepAgentNode` | Shared IEM routing contract — extract to mixin is optional, not required |
| Duplicate context building (`_build_conversation_context`, `_build_agent_results_context`, `_create_agent_result`) | Same four agent nodes | Common agent execution pattern; unification is optional |
| `AsyncBridge` (`get_async_bridge()`) global accessor from nodes/tools | Nodes wrapping async SDKs (Claude, A2A, MCP), tool executor, `AgentCapableMixin` | Sync graph nodes calling async SDKs need a runtime bridge; not a layer violation |
| `McpProvider` referenced directly in node code | `CustomAgentNode`, `DeepAgentNode` | Internal domain abstraction wrapping raw MCP SDK; nodes depend on provider, not SDK |
| `a2a.types.AgentCard` in node config | `A2AAgentNode` config + card builder | A2A protocol type needed for blueprint config validation; no pure-domain alternative exists |
| Parallel phase provider implementations (~1300 LOC each) | `OrchestratorPhaseProvider`, `UnifiedPhaseProvider` | Two context-building strategies for different node archetypes; single interface, two implementations |

## Boundaries

**Owns:** all agent capabilities, LLM integrations, tool implementations, node execution, catalog discovery.
**Does NOT own:** graph state schema (engine), session lifecycle (session), infrastructure adapters (adapters).
