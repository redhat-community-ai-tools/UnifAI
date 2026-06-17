---
service: mas
type: APP
code_root: multi-agent/
sections:
  quick_reference: 30
  connections: 41
  features: 54
  job_description: 62
  endpoints_90: 137
  port_abstractions_4: 279
  file_path_patterns: 288
  architecture: 309
  class_architecture: 448
---

# Multi Agent System (MAS)

> Multi-agent orchestration

| Field | Value |
|-------|-------|
| ID | `mas` |
| Type | APP |
| Tech Stack | Flask, LangGraph, Temporal, MongoDB, Redis, claude-agent-sdk, deepagents |
| Code Root | `multi-agent/` |
| Shares Codebase With | temporal_worker |
| Subtitle | Flask • Gunicorn • LangGraph / Temporal • Claude SDK • Deep Agents • Port 8002 |

## Quick Reference

| Item | Path |
|------|------|
| Code Root | `multi-agent/` |
| Composition Root | `multi-agent/bootstrap/container.py` |
| Flask Factory | `multi-agent/adapters/inbound/flask/flask_app.py` |
| App Config | `multi-agent/config/app_config.py` |
| Shared Config | `global_utils/src/global_utils/config/config.py` |
| Entry Points | `multi-agent/run/wsgi.py`, `multi-agent/run/dev.py`, `multi-agent/run/scripts/main.py` |

## Connections

**Incoming:**
- `ui` → `mas` *(/api2)*

**Outgoing:**
- `mas` → `identity` *(team auth)*
- `mas` → `rag` *(query.match)*
- `mas` → `mongodb` *(sessions)*
- `mas` → `redis` *(streams)*
- `mas` → `temporal` *(submit WF)*
- `mas` → `temporal_worker` *(shared codebase)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses
- **Agentic AI Inventory** — Browse & configure AI building blocks
- **Overview Dashboards** — Stats & monitoring for RAG and Agentic AI
- **Team Workspace** — Shared team identity & real-time collaboration
- **Agentic AI Workflows** — Build & manage blueprint graphs

## Job Description

The **Multi-Agent System (MAS)** is the core orchestration engine of UnifAI. It lets users design *blueprints* — visual graphs of AI agent workflows — execute them against LLMs, tools, and retrievers, and stream results in real time.

#### Core Domain Concepts

- **Blueprint** — a declarative YAML graph definition with nodes (agents, tools, retrievers), edges, and conditional routing. Blueprints are portable, versionable, and shareable. `BlueprintDraft` uses `$ref:` to point to resources; `BlueprintSpec` is the fully-resolved form.
- **Resource** — a configured building block in the agent inventory (LLMs, tools, providers, retrievers, conditions, nodes, auths). Each has a `cfg_dict` validated against its element schema.
- **Session** — a running instance of a blueprint. Contains `GraphState` (messages, output, inter_packets, threads, workspaces) and streams events via NDJSON.
- **Element Catalog** — auto-discovered plugin registry of all available element types across 8 categories.
- **Template** — a parameterized blueprint factory. Users fill a form, and `materialize()` creates a blueprint + resources in one step.
- **Actions** — independent operations (auth flows, MCP/RAG connection checks) linked to element types.

#### Element Categories

- **Nodes** — user_question, custom_agent (ReAct/Plan-and-Execute), orchestrator, a2a_agent, claude_agent (Claude SDK autonomous sessions), deep_agent (LangChain Deep Agents), merger, final_answer, branch_chooser
- **LLMs** — openai, google_genai, mock
- **Tools** — mcp_proxy, ssh_exec, web_fetch, oc_exec + builtins (workplan, topology, delegation, time)
- **Providers** — mcp_server (auto-discovers tools), rag_client, a2a_agent
- **Conditions** — router_boolean, router_direct (IEM-driven), threshold
- **Retrievers** — docs_rag, slack
- **Auths** — oauth_client, google_oauth, github_oauth, jira_oauth

#### Session Execution Flow

When a user sends a message, this is what happens end-to-end:

- **1.** UI calls `POST /sessions/user.session.submit` → MAS returns 202 with workflow ID
- **2.** MAS queues a Temporal workflow (or runs LangGraph in-process)
- **3.** UI subscribes via `GET /sessions/session.subscribe` (NDJSON stream)
- **4.** Worker executes **graph supersteps**: PLAN → EXECUTE (parallel) → UPDATE (merge)
- **5.** `UserQuestionNode` broadcasts a `TaskPacket` via IEM to adjacent agents
- **6.** `RouterDirectCondition` routes to agents with pending packets
- **7.** `CustomAgentNode` runs ReAct loop: LLM → tool calls → respond via IEM
- **8.** `FinalAnswerNode` collects results, merges into `output` + `messages`
- **9.** Events stream through Redis → NDJSON → UI (llm_token, tool_calling, complete)
- **10.** Final `GraphState` persisted to MongoDB

#### IEM — Inter-Element Messaging

Nodes communicate via **typed packets** in `GraphState.inter_packets`, not by writing to shared state. The dominant type is `TaskPacket` — carries a natural-language `Task` with thread_id, correlation, and response tracking. Adjacency is enforced (non-adjacent sends raise `IEMAdjacencyException`). `RouterDirectCondition` follows IEM traffic to decide which nodes run next, enabling message-driven re-entrancy (orchestrator ↔ agents loops).

#### Execution Mode

The configured default is **Background (Temporal)** — `engine_name=temporal`.

- **Background (Temporal) — default** — distributed, durable. `TemporalSessionEngine` submits `SessionWorkflow` → `GraphTraversalWorkflow`. Workers are stateless; each activity rebuilds the node from a serialized mini-blueprint.
- **Foreground (LangGraph) — fallback** — in-process, callables bound in `RTGraphPlan`. Used when Temporal is unavailable or for dev/simple graphs.

#### Identity, Collaboration & Sharing

- All data is scoped by **Identity** (user or team). Team mode uses `IdentityProvider` for membership checks.
- **Collaboration** — session presence, edit locks, typing indicators via Redis. Team sessions enforce busy-state semantics (LOCKED / IN_USE).
- **Sharing** — invite-based with `ShareCloner` deep-copy and RID remapping. Direct share-to-team also supported.
- **Templates** — marketplace of parameterized blueprints for one-click workflow creation.

#### User Journey

- **1. Define Goal** — what problem, which data sources, how many agents
- **2. Know Building Blocks** — browse `/inventory` catalog (LLMs, agents, tools, etc.)
- **3. Set Up Inventory** — create and configure resources
- **4. Build Workflow** — visual graph builder at `/agentic-ai` with live YAML validation
- **5. Chat with Workflow** — real-time execution at `/agentic-chats`

#### Integrations

- **RAG** — document retrieval via `docs_rag` and `slack` retrievers
- **LLM providers** — OpenAI, Google Gemini via LangChain wrappers
- **Claude Agent SDK** — autonomous coding agent sessions via Anthropic Claude on Vertex AI (`claude_agent_node`)
- **LangChain Deep Agents** — planning-capable agent delegation with built-in subagents and shell/filesystem (`deep_agent_node`)
- **A2A protocol** — remote agent delegation via `a2a_agent` nodes
- **MCP protocol** — external tool invocation via `mcp_server` providers (SSE/HTTP)
- **Identity service** — team membership, user directory, OAuth callback relay
- **SSH / OpenShift** — remote command execution via `ssh_exec` and `oc_exec` tools

## Endpoints (90)

### Sessions

| Method | Path | Summary |
|--------|------|--------|
| POST | `/sessions/user.session.create` | create session record |
| POST | `/sessions/user.session.submit` | execute via Temporal (default, 202) |
| POST | `/sessions/user.session.execute` | foreground fallback, sync or NDJSON stream |
| POST | `/sessions/session.cancel` | cancel Temporal workflow |
| GET | `/sessions/session.state.get` | full GraphState |
| GET | `/sessions/session.chat.get` | messages + output + status |
| GET | `/sessions/session.status.get` | status enum |
| GET | `/sessions/session.user.list` | all sessions for identity |
| GET | `/sessions/session.user.blueprints.get` | blueprint IDs in use |
| GET | `/sessions/session.subscribe` | late-join NDJSON stream |
| GET | `/sessions/session.stream.status` | Redis stream metadata |
| GET | `/sessions/session.stream.active` | list active streams |
| GET | `/sessions/session.meta` | get session metadata |
| POST | `/sessions/session.meta` | update metadata + typing sync |
| DEL | `/sessions/session.delete` |  |

### Blueprints

| Method | Path | Summary |
|--------|------|--------|
| POST | `/blueprints/blueprint.save` | save new draft |
| PUT | `/blueprints/blueprint.update` | update existing |
| GET | `/blueprints/available.blueprints.get` | full docs for workspace |
| GET | `/blueprints/available.blueprints.summary.get` | lightweight list |
| GET | `/blueprints/available.blueprints.resolved.get` | $ref resolved |
| GET | `/blueprints/blueprint.info.get` | single doc by ID |
| GET | `/blueprints/blueprint.draft.schema.get` | JSON Schema |
| DEL | `/blueprints/remove.blueprint` |  |
| PUT | `/blueprints/blueprint.metadata.set` |  |
| POST | `/blueprints/blueprint.validate` | validate all elements |
| POST | `/blueprints/draft.validate` | validate before saving |

### Resources

| Method | Path | Summary |
|--------|------|--------|
| POST | `/resources/resource.save` | create resource |
| GET | `/resources/resource.get` | single by ID |
| GET | `/resources/resources.list` | filtered + paginated |
| PUT | `/resources/resource.update` | update config/name |
| DEL | `/resources/resource.delete` | fails if in use |
| POST | `/resources/resource.validate` | validate + deps |
| POST | `/resources/resources.validate` | parallel batch |
| GET | `/resources/resource.card` | element card |
| POST | `/resources/resources.cards` | batch cards |
| POST | `/resources/config.validate` | pre-save validation |
| GET | `/resources/resource.schema` | JSON Schema |

### Catalog

| Method | Path | Summary |
|--------|------|--------|
| GET | `/catalog/categories.list.get` | all categories |
| GET | `/catalog/elements.list.get` | elements by category |
| GET | `/catalog/element.spec.get` | full spec + JSON Schema |

### Templates

| Method | Path | Summary |
|--------|------|--------|
| GET | `/templates/templates.list` | browse catalog |
| GET | `/templates/templates.search` | full-text search |
| GET | `/templates/templates.count` |  |
| GET | `/templates/template.get` | full template |
| GET | `/templates/template.summary.get` |  |
| POST | `/templates/template.create` |  |
| DEL | `/templates/template.delete` |  |
| GET | `/templates/template.schema.get` | input JSON Schema |
| POST | `/templates/template.input.validate` |  |
| POST | `/templates/template.instantiate` | preview (no save) |
| POST | `/templates/template.materialize` | create blueprint + resources |

### Shares

| Method | Path | Summary |
|--------|------|--------|
| POST | `/shares/share.create` | create invitation |
| POST | `/shares/share.accept` | accept + clone |
| POST | `/shares/share.decline` |  |
| POST | `/shares/share.to_team` | direct team share |
| POST | `/shares/share.cancel` |  |
| GET | `/shares/shares.list` | sent/received invites |
| GET | `/shares/share.get` | single invite |

### Collaboration — Presence

| Method | Path | Summary |
|--------|------|--------|
| POST | `/collaboration/session.join` |  |
| POST | `/collaboration/session.leave` |  |
| POST | `/collaboration/session.heartbeat` |  |
| GET | `/collaboration/session.participants` |  |
| GET | `/collaboration/team.sessions` |  |
| GET | `/collaboration/user.active_sessions` |  |
| POST | `/collaboration/session.typing` | set indicator |
| GET | `/collaboration/session.typing` | get typing users |
| GET | `/collaboration/health` | Redis availability |

### Collaboration — Edit Locks

| Method | Path | Summary |
|--------|------|--------|
| POST | `/collaboration/edit_lock.acquire` |  |
| POST | `/collaboration/edit_lock.release` |  |
| POST | `/collaboration/edit_lock.heartbeat` | renew |
| GET | `/collaboration/edit_lock.status` |  |
| POST | `/collaboration/edit_lock.statuses` | batch |

### Graph Validation

| Method | Path | Summary |
|--------|------|--------|
| GET | `/graph/validation/names.get` | validator names |
| POST | `/graph/validation/all.validate` | full topology |
| POST | `/graph/validation/channels.validate` |  |
| POST | `/graph/validation/dependencies.validate` |  |
| POST | `/graph/validation/cycles.validate` |  |
| POST | `/graph/validation/orphans.validate` |  |
| POST | `/graph/validation/required_nodes.validate` |  |

### Actions, Stats, Credentials, Health, Workspace

| Method | Path | Summary |
|--------|------|--------|
| GET | `/actions/actions.list` | list available actions |
| POST | `/actions/action.execute` | sync execution |
| GET | `/statistics/stats.get` | user dashboard |
| GET | `/statistics/stats.system.get` | admin analytics |
| POST | `/credentials/exchange` | OAuth code exchange |
| GET | `/credentials/status` | credential health |
| POST | `/credentials/client-config.save` | OAuth client config |
| GET | `/credentials/client-config.get` |  |
| DEL | `/workspace/workspace.cleanup` | purge identity data |
| GET | `/health/` | liveness |
| GET | `/health/version` |  |

## Port Abstractions (4)

| Port | Role | Adapter |
|------|------|--------|
| `ResourcesService` | CRUD with schema validation, dependency resolution, auth credential cleanup. Delete-guarded: cannot remove resources in use by blueprints. | — |
| `TemplateService` | create, instantiate (preview), materialize (saves blueprint + resources). Placeholder substitution engine. Text search index for catalog browsing. | — |
| `StatisticsService` | facade over BlueprintService, SessionService, ResourcesService. User scope + admin system-wide analytics. No own persistence. | — |
| `ActionsService` | auto_discover, execute_action_sync. Registered: AuthenticateAction, ValidateConnectionAction, GetToolsNamesAction (MCP). Linked by (category, type). | — |

## File Path Patterns

| Category | Path |
|----------|------|
| Endpoints | `multi-agent/adapters/inbound/flask/endpoints/**/*.py` |
| Ports | `multi-agent/lib/mas/**/ports.py`, `multi-agent/lib/mas/**/repository*.py`, `multi-agent/lib/mas/**/protocols.py`, `multi-agent/lib/mas/**/interfaces.py` |
| Composition Root | `multi-agent/bootstrap/container.py` |
| Flask Factory | `multi-agent/adapters/inbound/flask/flask_app.py` |
| App Config | `multi-agent/config/app_config.py` |
| Mongo Adapters | `multi-agent/adapters/outbound/mongo/*.py` |
| Element Specs | `multi-agent/lib/mas/elements/**/spec/*.py` |
| Elements — nodes | `multi-agent/lib/mas/elements/nodes/**` |
| Elements — llms | `multi-agent/lib/mas/elements/llms/**` |
| Elements — tools | `multi-agent/lib/mas/elements/tools/**` |
| Elements — providers | `multi-agent/lib/mas/elements/providers/**` |
| Elements — conditions | `multi-agent/lib/mas/elements/conditions/**` |
| Elements — retrievers | `multi-agent/lib/mas/elements/retrievers/**` |
| Elements — auths | `multi-agent/lib/mas/elements/auths/**` |
| Temporal Workflows | `multi-agent/adapters/inbound/temporal/workflows/*.py` |
| Temporal Activities | `multi-agent/adapters/inbound/temporal/activities/*.py` |

## Architecture

#### Design Pattern: Hexagonal Architecture

MAS uses **ports and adapters** (hexagonal architecture). Domain logic lives in `lib/mas/` with zero infrastructure imports. Technology adapters in `adapters/` implement the port interfaces. The composition root `bootstrap/container.py` wires everything at startup.

#### Directory Layout

- **`lib/mas/`** — The hexagon: 17 domain cores. ~200 Python files across blueprints, sessions, graph engine, elements, catalog, IEM, auth, collaboration, sharing, templates, validation, statistics, actions.
- **`adapters/inbound/`** — Flask HTTP endpoints + Temporal worker (workflows + activities).
- **`adapters/outbound/`** — MongoDB repos (7), Redis (streams, collab, auth state), LangGraph compiler, Temporal submitter, Identity HTTP, OAuth2.
- **`bootstrap/`** — `container.py` (AppContainer singleton) + `cli.py` (Typer CLI).

#### All 17 Hexagonal Domain Cores

**core/identity — Identity & Team Membership**

`IdentityProvider` port: `is_member`, `get_team_ids`, `resolve_team_id`. Almost every entity carries an Identity. Adapters: IdentityPodProvider (HTTP), DevIdentityProvider, NoOpIdentityProvider.

**core/auth — Authentication & Credentials**

Ports: `AuthStrategy`, `CredentialStore`, `ServerConfigStore`, `HttpClient`, `FlowStateStore`. Service: `AuthService` — OAuth2/PKCE/DCR, token refresh, API key. Elements depend on `AuthCredential` protocol, not OAuth specifics.

**core/channels — Event Streaming**

`ChannelFactory` / `SessionChannel` ports. Decouples producers (nodes) from consumers (HTTP subscribers). Adapters: `RedisChannelFactory` (Redis Streams) or `LocalChannelFactory` (in-process). This is how the same code runs locally or at scale.

**core/iem — Inter-Element Messaging**

`InterMessenger`: send_packet, inbox, process, acknowledge. Packets stored in `GraphState.inter_packets`. Types: `TaskPacket` (dominant), `SystemPacket`, `DebugPacket`. Adjacency-enforced. Enables orchestrator ↔ agent loops via `RouterDirectCondition`.

**core/ref — Reference Resolution**

`Ref` hierarchy: NodeRef, LLMRef, ToolRef, ProviderRef, RetrieverRef, ConditionRef. `RefWalker` resolves `$ref:resource_id` during Draft → Spec transformation.

**blueprints — Workflow Definitions**

Port: `BlueprintRepository`. Service: `BlueprintService` — save_draft, load_resolved, validate. Models: `BlueprintDraft` ($ref) → `BlueprintSpec` (resolved) → `GraphPlan`. Central to the build and execution lifecycle.

**resources — Agent Inventory**

Port: `ResourceRepository`. Service: `ResourcesService` — CRUD with schema validation, dependency resolution, auth credential cleanup. Delete-guarded: cannot remove resources in use by blueprints.

**session — Session Lifecycle**

Ports: `SessionRepository`, `BackgroundSessionEngine`. Service: `SessionService` — create, submit (bg, default), run (fg, fallback), cancel. Two-phase: `SessionInputProjector` stages inputs, then `BackgroundSessionEngine` (default) or `ForegroundSessionRunner` (fallback) executes. Status: PENDING → QUEUED → RUNNING → COMPLETED/FAILED/CANCELLED.

**engine — Graph Execution**

Ports: `BaseGraphBuilder`, `BaseGraphExecutor`. Shared BSP/Pregel algorithm (`GraphTraversal`): PLAN → EXECUTE (parallel) → UPDATE (channel merge). Two backends: Temporal (distributed, stateless workers — default) and LangGraph (in-process — fallback).

**graph — Construction & Validation**

`GraphService` — build_plan from BlueprintSpec. `GraphValidationService` — topology validators: dependencies, cycles, orphans, channels, required_nodes. Plugin-based with `FixSuggestionProvider`.

**catalog / elements — Plugin Architecture**

`ElementRegistry` — in-process singleton, auto-populated via `SpecDiscoverer`. Each element type is its own mini-domain. `BaseElementSpec` declares category, type_key, config_schema, factory_cls. `CatalogService` provides read API.

**collaboration — Multi-User Coordination**

Port: `CollaborationStore`. Service: `CollaborationService` — join/leave session, heartbeat, typing, edit locks. Redis keys: `mas:collab:session:{id}:*`, `mas:collab:editlock:*`. TTL-based presence.

**sharing — Cross-Identity Sharing**

Port: `ShareRepository`. Service: `ShareService` — create/accept/decline invites, share_to_team. `ShareCloner` deep-copies with RID remapping. TTL auto-expiry via MongoDB index.

**templates — Blueprint Factories**

Port: `TemplateRepository`. Service: `TemplateService` — create, instantiate (preview), materialize (saves blueprint + resources). Placeholder substitution engine. Text search index for catalog browsing.

**validation — Element Config Validation**

`ElementValidationService` — validates element configs (connectivity, credentials, deps) via per-spec `ElementValidator` plugins from registry. **Separate from** graph topology validation.

**statistics — Dashboard Aggregation**

`StatisticsService` — facade over BlueprintService, SessionService, ResourcesService. User scope + admin system-wide analytics. No own persistence.

**actions — Discoverable Operations**

Port: `BaseAction`. Service: `ActionsService` — auto_discover, execute_action_sync. Registered: AuthenticateAction, ValidateConnectionAction, GetToolsNamesAction (MCP). Linked by (category, type).

#### Port → Adapter Wiring

| Port | Adapter | Tech |
|---|---|---|
| `BlueprintRepository` | MongoBlueprintRepository | MongoDB |
| `ResourceRepository` | MongoResourceRepository | MongoDB |
| `SessionRepository` | MongoSessionRepository | MongoDB |
| `ShareRepository` | MongoShareRepository | MongoDB |
| `TemplateRepository` | MongoTemplateRepository | MongoDB |
| `CredentialStore` | MongoCredentialStore | MongoDB + Fernet |
| `ServerConfigStore` | MongoServerConfigStore | MongoDB |
| `FlowStateStore` | RedisFlowStateStore | Redis |
| `ChannelFactory` | Redis / LocalChannelFactory | Redis Streams / in-proc |
| `CollaborationStore` | RedisCollaborationStore | Redis |
| `BackgroundSessionEngine` | TemporalSessionEngine | Temporal |
| `IdentityProvider` | IdentityPodProvider / Dev | HTTP / in-proc |
| `AuthStrategy` | OAuth2Strategy / ApiKeyStrategy | httpx / in-proc |
| `BaseGraphBuilder` | TemporalBuilder (default) / LangGraph (fallback) | Temporal / LangGraph |
| `HttpClient` | HttpxAuthClient | httpx |

#### MongoDB Collections (7)

| Collection | Key Fields | Notable |
|---|---|---|
| blueprints | blueprint_id, identity, spec_dict, rid_refs | Unique on blueprint_id |
| workflow_sessions | run_id, identity, blueprint_id, graph_state, status | Unique on run_id; compound identity+time index |
| resources | rid, identity, category, type, name, cfg_dict | Unique on identity+category+type+name |
| shares | share_id, sender/recipient_identity, status | TTL auto-expiry on expires_at |
| templates | template_id, draft, placeholders, metadata | Text search on name+description |
| credentials | user_id, server_identifier, tokens (encrypted) | Fernet-encrypted access/refresh tokens |
| server_configs | server_identifier, client_id/secret, endpoints | OAuth client configurations |

#### Two Validation Domains

**Element validation** (`ElementValidationService`) checks individual resource configs — connectivity, credentials, dependency health. **Graph validation** (`GraphValidationService`) checks topology — cycles, orphans, missing channels, required start/end nodes. They run at different lifecycle stages and are a common source of confusion for new developers.

#### Blueprint Transformation Pipeline

`BlueprintDraft` ($ref) → `RefWalker` → `BlueprintSpec` (resolved) → `GraphService.build_plan()` → `GraphPlan` → `SessionElementBuilder` (factories) → `RTGraphPlan` (bound callables) → `GraphBuilderFactory` → LangGraph or Temporal graph.

#### Key Configuration (AppConfig)

| Setting | Default | Purpose |
|---|---|---|
| `engine_name` | temporal | Graph engine: temporal or langgraph |
| `temporal_task_queue` | graph-engine | Temporal worker queue name |
| `redis_stream_ttl` | 3600 | Redis stream TTL (seconds) |
| `identity_provider_mode` | (auto) | pod / dev / noop |
| `credential_encryption_key` | (empty) | Fernet key for token encryption |
| `collaboration_presence_ttl` | 300 | Presence key TTL (seconds) |
| `collaboration_edit_lock_ttl_sec` | 180 | Edit lock TTL (seconds) |

#### Graceful Degradation

Redis, Temporal, and Identity degrade gracefully if unavailable. Without Temporal: falls back to foreground-only execution via LangGraph (no `submit()`). Without Redis: in-process channels only, no collaboration, no stream subscriptions. Without Identity pod: DevIdentityProvider (all team checks pass). The service remains functional in a minimal **Mongo-only** configuration, but the recommended production stack includes Temporal + Redis.

## Class Architecture

MAS follows **hexagonal architecture** with a rich domain layer in `lib/mas/` (~200 Python files, 17 domain cores). The element plugin system uses auto-discovery to register node types including external SDK integrations: **ClaudeAgentNode** (Anthropic Claude via Vertex AI) and **DeepAgentNode** (LangChain Deep Agents). Two execution backends — **Temporal** (distributed, default) and **LangGraph** (in-process, fallback) — share the same BSP graph traversal algorithm. Inbound: Flask + Temporal worker. Outbound: MongoDB (7 collections), Redis (streams, collab, auth), Temporal, LangGraph, Identity HTTP, OAuth2, Vertex AI, deepagents.

### Key Extension Points

These are the base classes and ABCs that new code should extend or implement:

| Class | File | Layer | Implementations / Subclasses |
|-------|------|-------|------------------------------|
| `BlueprintRepository (ABC)` | `lib/mas/blueprints/repository/repository.py` | Blueprints | `MongoBlueprintRepository` |
| `BaseGraphBuilder (ABC)` | `lib/mas/engine/domain/base_builder.py` | Execution Engine | `LangGraphBuilder`, `TemporalGraphBuilder` |
| `BaseGraphExecutor (ABC)` | `lib/mas/engine/domain/base_executor.py` | Execution Engine | `ForegroundSessionRunner` |
| `IdentityProvider (ABC)` | `lib/mas/core/identity/ports.py` | Identity & Collaboration | `IdentityPodProvider`, `DevIdentityProvider`, `CollaborationService`, `ShareService` |
| `CollaborationStore (ABC)` | `lib/mas/collaboration/ports.py` | Identity & Collaboration | `RedisCollaborationStore` |
| `BaseElementSpec (ABC)` | `lib/mas/elements/common/base_element_spec.py` | Elements Plugin Layer | `element specs (nodes, llms, tools, providers, conditions, retrievers, auths)` |
| `BaseFactory (ABC)` | `lib/mas/elements/common/base_factory.py` | Elements Plugin Layer | `element factories (nodes, llms, tools, providers, conditions, retrievers, auths)` |
| `BaseNode` | `lib/mas/elements/nodes/common/base_node.py` | Elements Plugin Layer | `CustomAgentNode`, `OrchestratorNode`, `A2AAgentNode`, `ClaudeAgentNode`, `DeepAgentNode`, `UserQuestionNode`, `FinalAnswerNode`, `MergerNode`, `BranchChooserNode` |
| `BaseTool (ABC)` | `lib/mas/elements/tools/common/base_tool.py` | Elements Plugin Layer | `McpProxyTool`, `WebFetchTool`, `SshExecTool`, `OcExecTool` |
| `AgentStrategy (ABC)` | `lib/mas/elements/nodes/common/agent/strategies/` | Elements Plugin Layer | `AgentRunner` |

### Bootstrap

| Class | File | Role |
|-------|------|------|
| `AppContainer` | `bootstrap/container.py` | Singleton composition root: wires all services, repos, and adapters. Auth wired last via set_auth_service() callbacks. |

- `AppContainer` calls: `SessionService`, `BlueprintService`, `ResourcesService`, `AuthService`, `CollaborationService`, `ChannelFactory`, `ElementRegistry`, `MongoBlueprintRepository`, `MongoSessionRepository`, `MongoResourceRepository`, `MongoShareRepository`, `MongoTemplateRepository`, `MongoCredentialStore`, `MongoServerConfigStore`, `RedisChannelFactory`, `RedisCollaborationStore`, `TemporalSessionEngine`, `IdentityPodProvider`
- `AppContainer` called by: `entrypoint`

### Catalog & Discovery

| Class | File | Role |
|-------|------|------|
| `ElementRegistry` | `lib/mas/catalog/element_registry.py` | Thread-safe singleton of all BaseElementSpec subclasses by category/type |
| `SpecDiscoverer` | `lib/mas/catalog/spec_discoverer.py` | Scans elements/**/spec/ packages to auto-register element specs |
| `CatalogService` | `lib/mas/catalog/service.py` | Read API for catalog listings and schemas |
| `ElementCardService` | `lib/mas/catalog/card_service.py` | Builds element cards (identity, skills, capabilities) from specs |

- `ElementRegistry` calls: `BaseElementSpec`, `BaseFactory`
- `ElementRegistry` called by: `AppContainer`, `CatalogService`, `GraphService`, `WorkflowSessionFactory`, `SessionElementBuilder`, `ElementValidationService`, `ActionsService`, `TemplateService`, `ElementCardService`

### Blueprints

| Class | File | Role |
|-------|------|------|
| `BlueprintService` | `lib/mas/blueprints/service.py` | CRUD + validation orchestration for blueprints |
| `BlueprintResolver` | `lib/mas/blueprints/resolver.py` | Resolves $ref: resource references into full configs |
| `BlueprintRepository (ABC)` | `lib/mas/blueprints/repository/repository.py` | Port for blueprint persistence (identity-scoped) |

- `BlueprintService` calls: `BlueprintRepository`, `BlueprintResolver`, `ElementValidationService`, `AuthService`
- `BlueprintService` called by: `HTTP: /blueprints/`, `UserSessionManager`, `TemplateService`, `ShareService`, `ShareCloner`, `StatisticsService`

### Graph Planning & Validation

| Class | File | Role |
|-------|------|------|
| `GraphService` | `lib/mas/graph/service.py` | Facade: builds GraphPlan from BlueprintSpec |
| `PlanBuilder` | `lib/mas/graph/plan_builder.py` | Constructs logical graph plan with steps, edges, conditions |
| `GraphValidationService` | `lib/mas/graph/validation/service.py` | Orchestrates topology validators (cycles, orphans, channels, deps, required_nodes) |
| `GraphTraversal` | `lib/mas/engine/distributed/traversal.py` | BSP superstep algorithm: PLAN → EXECUTE (parallel) → UPDATE (merge). Shared by both engines. |

### IEM — Inter-Element Messaging

| Class | File | Role |
|-------|------|------|
| `DefaultInterMessenger` | `lib/mas/core/iem/messenger.py` | State-based messenger: send/receive/acknowledge packets via GraphState.inter_packets |
| `TaskPacket` | `lib/mas/core/iem/packets.py` | Dominant IEM packet: carries workload Task payload between nodes |
| `ElementAddress` | `lib/mas/core/iem/packets.py` | Typed source/destination address for IEM routing |
| `IEMCapableMixin` | `lib/mas/elements/nodes/common/mixins/` | Mixin that provides get_messenger() to nodes; reads/writes INTER_PACKETS channel |
| `RouterDirectCondition` | `lib/mas/elements/conditions/router_direct/` | Routes to nodes with unacknowledged outgoing IEM packets — enables message-driven re-entrancy |

- `TaskPacket` called by: `UserQuestionNode`, `CustomAgentNode`, `OrchestratorNode`, `FinalAnswerNode`

### Session Management

| Class | File | Role |
|-------|------|------|
| `SessionService` | `lib/mas/session/service.py` | Application boundary: create/submit (default)/run (fallback)/cancel/list/stats |
| `UserSessionManager` | `lib/mas/session/management/user_session_manager.py` | Creates sessions, loads SessionRecord, uses factory + blueprint |
| `WorkflowSessionFactory` | `lib/mas/session/building/workflow_session_factory.py` | Builds WorkflowSession, RTGraphPlan, or bare SessionRegistry |
| `SessionElementBuilder` | `lib/mas/session/building/element_builder.py` | Topologically sorts CategoryBuilders, instantiates runtime elements from BlueprintSpec |
| `SessionInputProjector` | `lib/mas/session/execution/input_projector.py` | Stages user inputs into session state before execution |
| `BackgroundSessionRunner` | `lib/mas/session/execution/background_runner.py` | Orchestrates session lifecycle for Temporal background execution (default path) |
| `ForegroundSessionRunner` | `lib/mas/session/execution/foreground_runner.py` | Runs graph in-process with streaming via ChannelFactory (fallback path) |
| `SessionLifecycle` | `lib/mas/session/execution/lifecycle.py` | Persisted status transitions (PENDING→QUEUED→RUNNING→COMPLETED/FAILED/CANCELLED) |

- `SessionService` calls: `UserSessionManager`, `BackgroundSessionEngine`, `ForegroundSessionRunner`, `SessionInputProjector`
- `SessionService` called by: `HTTP: /sessions/`, `SessionWorkflow`, `StatisticsService`
- `UserSessionManager` calls: `WorkflowSessionFactory`, `BlueprintService`, `SessionRepository`
- `UserSessionManager` called by: `SessionService`
- `WorkflowSessionFactory` calls: `SessionElementBuilder`, `GraphBuilderFactory`, `PlanBuilder`
- `WorkflowSessionFactory` called by: `UserSessionManager`, `NodeExecutor`
- `ForegroundSessionRunner` calls: `BaseGraphExecutor`, `ChannelFactory`, `SessionLifecycle`
- `ForegroundSessionRunner` called by: `SessionService`

### Execution Engine

| Class | File | Role |
|-------|------|------|
| `BaseGraphBuilder (ABC)` | `lib/mas/engine/domain/base_builder.py` | Abstract: add_node/edge, compile_from_plan → executor |
| `BaseGraphExecutor (ABC)` | `lib/mas/engine/domain/base_executor.py` | Abstract: run(initial_state), get_state |
| `GraphBuilderFactory` | `lib/mas/engine/factory.py` | Selects concrete builder by engine name (temporal default / langgraph fallback) |
| `NodeExecutor` | `lib/mas/engine/distributed/node_executor.py` | Stateless worker handler: materializes mini-blueprint, runs single node |
| `NodeDeploymentExtractor` | `lib/mas/engine/distributed/deployment.py` | Builds mini-blueprints containing only a node's dependency closure |

### Resources & Auth

| Class | File | Role |
|-------|------|------|
| `ResourcesService` | `lib/mas/resources/service.py` | CRUD + validation + auth-aware resource operations |
| `ResourcesRegistry` | `lib/mas/resources/registry.py` | Low-level CRUD + delete guards (checks blueprint/resource usage) |
| `AuthService` | `lib/mas/core/auth/service.py` | Strategy-based auth (OAuth2, API key) with credential storage, token refresh, bind/bind_lazy |
| `OAuth2Strategy` | `adapters/outbound/auth/oauth2_strategy.py` | Full OAuth2/PKCE/DCR flow: initiate, complete, refresh, recovery |
| `ApiKeyStrategy` | `adapters/outbound/auth/api_key_strategy.py` | API key collection strategy |
| `ElementValidationService` | `lib/mas/validation/service.py` | Validates element configs (connectivity, credentials, deps) via per-spec validators |

- `ResourcesService` calls: `ResourcesRegistry`, `ElementValidationService`, `AuthService`, `ElementCardService`
- `ResourcesService` called by: `HTTP: /resources/`, `ShareService`, `TemplateService`, `ShareCloner`, `ResourceMaterializer`, `StatisticsService`
- `AuthService` calls: `AuthStrategyRegistry`, `CredentialStore`, `ServerConfigStore`, `AuthDetector`
- `AuthService` called by: `ResourcesService`, `BlueprintService`, `ProviderBuilder`
- `OAuth2Strategy` calls: `HttpxAuthClient`, `FlowStateStore`, `OAuthStateManager`
- `OAuth2Strategy` called by: `AuthStrategyRegistry`

### Identity & Collaboration

| Class | File | Role |
|-------|------|------|
| `Identity` | `lib/mas/core/identity/models.py` | Identity value object: type (user\|team), id, display_name. Pervasive across all persisted entities. |
| `IdentityProvider (ABC)` | `lib/mas/core/identity/ports.py` | Port: is_member, get_team_ids, resolve_team_id, resolve_team_display_name |
| `IdentityPodProvider` | `adapters/outbound/identity/identity_pod_provider.py` | HTTP adapter: calls Identity service for membership/resolution |
| `DevIdentityProvider` | `adapters/outbound/identity/dev_provider.py` | Dev stub: permits all membership checks, no auth required |
| `CollaborationService` | `lib/mas/collaboration/service.py` | Session presence, edit locks, typing indicators. Checks session access + team membership. |
| `CollaborationStore (ABC)` | `lib/mas/collaboration/ports.py` | Port: participants, team_sessions, typing, edit locks, health |

- `Identity` called by: `BlueprintService`, `SessionService`, `ResourcesService`, `ShareService`, `CollaborationService`
- `IdentityProvider (ABC)` called by: `IdentityPodProvider`, `DevIdentityProvider`, `CollaborationService`, `ShareService`
- `CollaborationService` calls: `CollaborationStore`, `SessionRepository`, `IdentityProvider`
- `CollaborationService` called by: `HTTP: /collaboration/`

### Sharing, Templates & Statistics

| Class | File | Role |
|-------|------|------|
| `ShareService` | `lib/mas/sharing/service.py` | Create/accept/decline invites, share_to_team. Invite-based with deep resource/blueprint cloning. |
| `ShareCloner` | `lib/mas/sharing/cloner.py` | Deep-copies resource graphs + blueprints into target identity with RID remapping |
| `TemplateService` | `lib/mas/templates/service.py` | CRUD + instantiate (preview) + materialize (saves blueprint + resources in one step) |
| `TemplateInstantiator` | `lib/mas/templates/instantiation/instantiator.py` | Placeholder substitution engine: fills template draft with user inputs |
| `ResourceMaterializer` | `lib/mas/templates/instantiation/resource_materializer.py` | Creates actual resources from template placeholder values during materialize |
| `StatisticsService` | `lib/mas/statistics/service.py` | Facade: user stats + admin system analytics. No own persistence. |
| `ActionsService` | `lib/mas/actions/service.py` | Auto-discover + execute action plugins (auth, MCP validate, tool discovery) |

- `ShareService` calls: `ShareCloner`, `ShareRepository`, `IdentityProvider`
- `ShareService` called by: `HTTP: /shares/`
- `TemplateService` calls: `TemplateRepository`, `TemplateInstantiator`, `ResourceMaterializer`, `BlueprintService`, `ElementRegistry`
- `TemplateService` called by: `HTTP: /templates/`
- `StatisticsService` calls: `BlueprintService`, `SessionService`, `ResourcesService`
- `StatisticsService` called by: `HTTP: /statistics/`

### Inbound Adapters — Temporal

| Class | File | Role |
|-------|------|------|
| `SessionWorkflow` | `adapters/inbound/temporal/workflows/session_workflow.py` | Parent workflow: begin → graph traversal → complete/fail lifecycle |
| `GraphTraversalWorkflow` | `adapters/inbound/temporal/workflows/graph_traversal_workflow.py` | Child workflow: BSP supersteps — plan, execute nodes, evaluate conditions, merge, repeat |
| `GraphNodeActivities` | `adapters/inbound/temporal/activities/graph_node_activities.py` | Activity bundle: execute_graph_node (15min timeout, heartbeats) and evaluate_condition |
| `SessionLifecycleActivities` | `adapters/inbound/temporal/activities/session_lifecycle_activities.py` | Activity bundle: begin/complete/fail session transitions |

- `SessionWorkflow` calls: `BackgroundSessionRunner`, `GraphTraversalWorkflow`, `SessionLifecycleActivities`
- `SessionWorkflow` called by: `Temporal: dispatch`

### Outbound Adapters — MongoDB

| Class | File | Role |
|-------|------|------|
| `MongoBlueprintRepository` | `adapters/outbound/mongo/blueprint_repository.py` | Blueprint persistence: blueprints collection. Indexes: blueprint_id (unique), rid_refs, identity+updated_at. |
| `MongoSessionRepository` | `adapters/outbound/mongo/session_repository.py` | Session persistence: workflow_sessions. System analytics via $facet/$dateTrunc aggregations. |
| `MongoResourceRepository` | `adapters/outbound/mongo/resource_repository.py` | Resource persistence: resources. Unique index on identity+category+type+name. |
| `MongoShareRepository` | `adapters/outbound/mongo/share_repository.py` | Share invites: shares collection. TTL auto-expiry on expires_at. |
| `MongoTemplateRepository` | `adapters/outbound/mongo/template_repository.py` | Template persistence: templates. Text search index on name+description. |
| `MongoCredentialStore` | `adapters/outbound/mongo/credential_store.py` | Credential persistence: credentials. Fernet-encrypted access/refresh tokens. |
| `MongoServerConfigStore` | `adapters/outbound/mongo/server_config_store.py` | OAuth client configs: server_configs. Unique on server_identifier. |

### Outbound Adapters — Redis, Engine, Identity

| Class | File | Role |
|-------|------|------|
| `RedisChannelFactory` | `adapters/outbound/channels/redis/factory.py` | Creates Redis Stream-backed session channels for distributed streaming |
| `LocalChannelFactory` | `adapters/outbound/channels/local/factory.py` | In-process channel factory (no Redis fallback) |
| `RedisCollaborationStore` | `adapters/outbound/redis/collaboration_store.py` | Redis-backed presence, typing, team sessions, edit locks. Keys: mas:collab:* |
| `RedisFlowStateStore` | `adapters/outbound/redis/flow_state_store.py` | Pending OAuth flow state. Keys: auth_pending:<state_hash>. Encrypted. |
| `TemporalSessionEngine` | `adapters/outbound/temporal/session_engine.py` | Submits SessionWorkflow to Temporal. Implements BackgroundSessionEngine port. Default execution path. |
| `LangGraphBuilder` | `adapters/outbound/langgraph/builder.py` | Wraps langgraph.StateGraph with node callables from RTGraphPlan (fallback engine) |
| `IdentityDirectoryClient` | `adapters/outbound/identity_directory_client.py` | HTTP client to Identity service for user/group directory lookups |

### Elements Plugin Layer

| Class | File | Role |
|-------|------|------|
| `BaseElementSpec (ABC)` | `lib/mas/elements/common/base_element_spec.py` | Declares category, type_key, config schema, factory_cls, reads/writes channels, validator_cls, card_builder_cls |
| `BaseFactory (ABC)` | `lib/mas/elements/common/base_factory.py` | accepts(cfg)/create(cfg, **deps) contract for all element plugins |
| `BaseNode` | `lib/mas/elements/nodes/common/base_node.py` | Wraps GraphState in permission-scoped StateView, calls run(). Channels via MRO. |
| `BaseTool (ABC)` | `lib/mas/elements/tools/common/base_tool.py` | Base for tool integrations (mcp_proxy, ssh_exec, web_fetch, oc_exec) |
| `BaseLLM` | `lib/mas/elements/llms/common/base_llm.py` | Base for LLM integrations (openai, google_genai, mock) |
| `BaseRetriever` | `lib/mas/elements/retrievers/common/base_retriever.py` | Base for retriever integrations (docs_rag, slack) |
| `McpProvider` | `lib/mas/elements/providers/mcp/runtime/mcp_provider.py` | MCP server client: discovers tools, creates McpProxyTool instances. SSE/HTTP transport. Live auth. |
| `ClaudeAgentNode` | `lib/mas/elements/nodes/claude_agent/claude_agent_node.py` | Autonomous Claude SDK sessions via Vertex AI. Session-scoped working dirs, skills repos, streaming. |
| `DeepAgentNode` | `lib/mas/elements/nodes/deep_agent/deep_agent_node.py` | LangChain Deep Agents with planning, subagent delegation, and LocalShellBackend. |
| `BaseLLMChatModelAdapter` | `lib/mas/elements/llms/common/langchain_adapter.py` | Bridges domain BaseLLM to LangChain BaseChatModel for DeepAgentNode |
| `LangChainToolsConverter` | `lib/mas/elements/tools/common/converter.py` | Converts domain BaseTool + MCP tools to LangChain StructuredTool format |
| `AgentStrategy (ABC)` | `lib/mas/elements/nodes/common/agent/strategies/` | Base agent execution strategy (ReAct, PlanAndExecute) |
| `AgentRunner` | `lib/mas/elements/nodes/common/agent/runner.py` | Executes agent loop: iterate actions until finish. Uses ToolExecutorManager. |
| `BuiltinTools` | `lib/mas/elements/tools/builtin/` | Runtime-only tools (not catalog entries): workplan, topology, delegation, workspace, time, retriever-as-tool |

- `BaseNode` calls: `StateView`
- `BaseNode` called by: `CustomAgentNode`, `OrchestratorNode`, `A2AAgentNode`, `ClaudeAgentNode`, `DeepAgentNode`, `UserQuestionNode`, `FinalAnswerNode`, `MergerNode`, `BranchChooserNode`
- `BaseTool (ABC)` called by: `McpProxyTool`, `WebFetchTool`, `SshExecTool`, `OcExecTool`
- `BaseLLM` called by: `OpenAILLM`, `GoogleGenAILLM`, `MockLLM`
- `McpProvider` calls: `McpServerClient`, `TransportFactory`, `AuthCredential`
- `McpProvider` called by: `ProviderBuilder`
- `ClaudeAgentNode` calls: `claude_agent_sdk`, `IEMCapableMixin`, `WorkloadCapableMixin`, `RetrieverCapableMixin`
- `ClaudeAgentNode` called by: `BaseNode`, `NodeExecutor`
- `DeepAgentNode` calls: `deepagents`, `BaseLLMChatModelAdapter`, `LangChainToolsConverter`, `IEMCapableMixin`, `WorkloadCapableMixin`
- `DeepAgentNode` called by: `BaseNode`, `NodeExecutor`
- `AgentRunner` calls: `AgentStrategy`, `AgentActionExecutor`, `ToolExecutorManager`
- `AgentRunner` called by: `CustomAgentNode`, `OrchestratorNode`

---

*Source: `js/data/services/mas.js`* | *Classes: `js/data-classes/mas.js`*
