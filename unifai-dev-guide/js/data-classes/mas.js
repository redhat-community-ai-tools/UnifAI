SERVICE_CLASSES.mas = {
  description: `<p>MAS follows <strong>hexagonal architecture</strong> with a rich domain layer in <code>lib/mas/</code> (~200 Python files, 17 domain cores). The element plugin system uses auto-discovery to register node types including external SDK integrations: <strong>ClaudeAgentNode</strong> (Anthropic Claude via Vertex AI) and <strong>DeepAgentNode</strong> (LangChain Deep Agents). Two execution backends — <strong>Temporal</strong> (distributed, default) and <strong>LangGraph</strong> (in-process, fallback) — share the same BSP graph traversal algorithm. Inbound: Flask + Temporal worker. Outbound: MongoDB (7 collections), Redis (streams, collab, auth), Temporal, LangGraph, Identity HTTP, OAuth2, Vertex AI, deepagents.</p>`,
  layers: [
    {
      name: 'Bootstrap',
      classes: [
        { name: 'AppContainer', file: 'bootstrap/container.py', role: 'Singleton composition root: wires all services, repos, and adapters. Auth wired last via set_auth_service() callbacks.', calls: ['SessionService', 'BlueprintService', 'ResourcesService', 'AuthService', 'CollaborationService', 'ChannelFactory', 'ElementRegistry', 'MongoBlueprintRepository', 'MongoSessionRepository', 'MongoResourceRepository', 'MongoShareRepository', 'MongoTemplateRepository', 'MongoCredentialStore', 'MongoServerConfigStore', 'RedisChannelFactory', 'RedisCollaborationStore', 'TemporalSessionEngine', 'IdentityPodProvider'], calledBy: ['entrypoint'] },
      ]
    },
    {
      name: 'Catalog & Discovery',
      classes: [
        { name: 'ElementRegistry', file: 'lib/mas/catalog/element_registry.py', role: 'Thread-safe singleton of all BaseElementSpec subclasses by category/type', calls: ['BaseElementSpec', 'BaseFactory'], calledBy: ['AppContainer', 'CatalogService', 'GraphService', 'WorkflowSessionFactory', 'SessionElementBuilder', 'ElementValidationService', 'ActionsService', 'TemplateService', 'ElementCardService'] },
        { name: 'SpecDiscoverer', file: 'lib/mas/catalog/spec_discoverer.py', role: 'Scans elements/**/spec/ packages to auto-register element specs', calls: ['importlib'], calledBy: ['ElementRegistry'] },
        { name: 'CatalogService', file: 'lib/mas/catalog/service.py', role: 'Read API for catalog listings and schemas', calls: ['ElementRegistry'], calledBy: ['HTTP: /catalog/'] },
        { name: 'ElementCardService', file: 'lib/mas/catalog/card_service.py', role: 'Builds element cards (identity, skills, capabilities) from specs', calls: ['ElementRegistry'], calledBy: ['ResourcesService', 'BlueprintService'] },
      ]
    },
    {
      name: 'Blueprints',
      classes: [
        { name: 'BlueprintService', file: 'lib/mas/blueprints/service.py', role: 'CRUD + validation orchestration for blueprints', calls: ['BlueprintRepository', 'BlueprintResolver', 'ElementValidationService', 'AuthService'], calledBy: ['HTTP: /blueprints/', 'UserSessionManager', 'TemplateService', 'ShareService', 'ShareCloner', 'StatisticsService'] },
        { name: 'BlueprintResolver', file: 'lib/mas/blueprints/resolver.py', role: 'Resolves $ref: resource references into full configs', calls: ['ResourcesRegistry', 'ElementRegistry'], calledBy: ['BlueprintService', 'WorkflowSessionFactory'] },
        { name: 'BlueprintRepository (ABC)', file: 'lib/mas/blueprints/repository/repository.py', role: 'Port for blueprint persistence (identity-scoped)', calls: [], calledBy: ['MongoBlueprintRepository'] },
      ]
    },
    {
      name: 'Graph Planning & Validation',
      classes: [
        { name: 'GraphService', file: 'lib/mas/graph/service.py', role: 'Facade: builds GraphPlan from BlueprintSpec', calls: ['ElementRegistry', 'PlanBuilder'], calledBy: ['HTTP: /graph/'] },
        { name: 'PlanBuilder', file: 'lib/mas/graph/plan_builder.py', role: 'Constructs logical graph plan with steps, edges, conditions', calls: ['ElementRegistry'], calledBy: ['GraphService', 'WorkflowSessionFactory'] },
        { name: 'GraphValidationService', file: 'lib/mas/graph/validation/service.py', role: 'Orchestrates topology validators (cycles, orphans, channels, deps, required_nodes)', calls: ['ValidationProvider', 'FixSuggestionProvider'], calledBy: ['HTTP: /graph/validation/', 'BlueprintService'] },
        { name: 'GraphTraversal', file: 'lib/mas/engine/distributed/traversal.py', role: 'BSP superstep algorithm: PLAN → EXECUTE (parallel) → UPDATE (merge). Shared by both engines.', calls: ['GraphNodeActivities', 'GraphDefinition'], calledBy: ['GraphTraversalWorkflow'] },
      ]
    },
    {
      name: 'IEM — Inter-Element Messaging',
      classes: [
        { name: 'DefaultInterMessenger', file: 'lib/mas/core/iem/messenger.py', role: 'State-based messenger: send/receive/acknowledge packets via GraphState.inter_packets', calls: ['MessengerMiddleware'], calledBy: ['IEMCapableMixin'] },
        { name: 'TaskPacket', file: 'lib/mas/core/iem/packets.py', role: 'Dominant IEM packet: carries workload Task payload between nodes', calls: [], calledBy: ['UserQuestionNode', 'CustomAgentNode', 'OrchestratorNode', 'FinalAnswerNode'] },
        { name: 'ElementAddress', file: 'lib/mas/core/iem/packets.py', role: 'Typed source/destination address for IEM routing', calls: [], calledBy: ['IEMCapableMixin'] },
        { name: 'IEMCapableMixin', file: 'lib/mas/elements/nodes/common/mixins/', role: 'Mixin that provides get_messenger() to nodes; reads/writes INTER_PACKETS channel', calls: ['DefaultInterMessenger'], calledBy: ['BaseNode'] },
        { name: 'RouterDirectCondition', file: 'lib/mas/elements/conditions/router_direct/', role: 'Routes to nodes with unacknowledged outgoing IEM packets — enables message-driven re-entrancy', calls: ['GraphState'], calledBy: ['GraphTraversal'] },
      ]
    },
    {
      name: 'Session Management',
      classes: [
        { name: 'SessionService', file: 'lib/mas/session/service.py', role: 'Application boundary: create/submit (default)/run (fallback)/cancel/list/stats', calls: ['UserSessionManager', 'BackgroundSessionEngine', 'ForegroundSessionRunner', 'SessionInputProjector'], calledBy: ['HTTP: /sessions/', 'SessionWorkflow', 'StatisticsService'] },
        { name: 'UserSessionManager', file: 'lib/mas/session/management/user_session_manager.py', role: 'Creates sessions, loads SessionRecord, uses factory + blueprint', calls: ['WorkflowSessionFactory', 'BlueprintService', 'SessionRepository'], calledBy: ['SessionService'] },
        { name: 'WorkflowSessionFactory', file: 'lib/mas/session/building/workflow_session_factory.py', role: 'Builds WorkflowSession, RTGraphPlan, or bare SessionRegistry', calls: ['SessionElementBuilder', 'GraphBuilderFactory', 'PlanBuilder'], calledBy: ['UserSessionManager', 'NodeExecutor'] },
        { name: 'SessionElementBuilder', file: 'lib/mas/session/building/element_builder.py', role: 'Topologically sorts CategoryBuilders, instantiates runtime elements from BlueprintSpec', calls: ['CategoryBuilder', 'ElementRegistry'], calledBy: ['WorkflowSessionFactory'] },
        { name: 'SessionInputProjector', file: 'lib/mas/session/execution/input_projector.py', role: 'Stages user inputs into session state before execution', calls: ['SessionRepository'], calledBy: ['SessionService'] },
        { name: 'BackgroundSessionRunner', file: 'lib/mas/session/execution/background_runner.py', role: 'Orchestrates session lifecycle for Temporal background execution (default path)', calls: ['BackgroundSessionOps'], calledBy: ['SessionWorkflow'] },
        { name: 'ForegroundSessionRunner', file: 'lib/mas/session/execution/foreground_runner.py', role: 'Runs graph in-process with streaming via ChannelFactory (fallback path)', calls: ['BaseGraphExecutor', 'ChannelFactory', 'SessionLifecycle'], calledBy: ['SessionService'] },
        { name: 'SessionLifecycle', file: 'lib/mas/session/execution/lifecycle.py', role: 'Persisted status transitions (PENDING→QUEUED→RUNNING→COMPLETED/FAILED/CANCELLED)', calls: ['SessionRepository'], calledBy: ['ForegroundSessionRunner', 'BackgroundLifecycleHandler'] },
      ]
    },
    {
      name: 'Execution Engine',
      classes: [
        { name: 'BaseGraphBuilder (ABC)', file: 'lib/mas/engine/domain/base_builder.py', role: 'Abstract: add_node/edge, compile_from_plan → executor', calls: [], calledBy: ['LangGraphBuilder', 'TemporalGraphBuilder'] },
        { name: 'BaseGraphExecutor (ABC)', file: 'lib/mas/engine/domain/base_executor.py', role: 'Abstract: run(initial_state), get_state', calls: [], calledBy: ['ForegroundSessionRunner'] },
        { name: 'GraphBuilderFactory', file: 'lib/mas/engine/factory.py', role: 'Selects concrete builder by engine name (temporal default / langgraph fallback)', calls: ['TemporalGraphBuilder', 'LangGraphBuilder'], calledBy: ['WorkflowSessionFactory'] },
        { name: 'NodeExecutor', file: 'lib/mas/engine/distributed/node_executor.py', role: 'Stateless worker handler: materializes mini-blueprint, runs single node', calls: ['WorkflowSessionFactory', 'SessionChannel'], calledBy: ['GraphNodeActivities'] },
        { name: 'NodeDeploymentExtractor', file: 'lib/mas/engine/distributed/deployment.py', role: 'Builds mini-blueprints containing only a node\'s dependency closure', calls: ['BlueprintSpec'], calledBy: ['TemporalGraphBuilder'] },
      ]
    },
    {
      name: 'Resources & Auth',
      classes: [
        { name: 'ResourcesService', file: 'lib/mas/resources/service.py', role: 'CRUD + validation + auth-aware resource operations', calls: ['ResourcesRegistry', 'ElementValidationService', 'AuthService', 'ElementCardService'], calledBy: ['HTTP: /resources/', 'ShareService', 'TemplateService', 'ShareCloner', 'ResourceMaterializer', 'StatisticsService'] },
        { name: 'ResourcesRegistry', file: 'lib/mas/resources/registry.py', role: 'Low-level CRUD + delete guards (checks blueprint/resource usage)', calls: ['ResourceRepository', 'BlueprintRepository'], calledBy: ['BlueprintResolver', 'ResourcesService'] },
        { name: 'AuthService', file: 'lib/mas/core/auth/service.py', role: 'Strategy-based auth (OAuth2, API key) with credential storage, token refresh, bind/bind_lazy', calls: ['AuthStrategyRegistry', 'CredentialStore', 'ServerConfigStore', 'AuthDetector'], calledBy: ['ResourcesService', 'BlueprintService', 'ProviderBuilder'] },
        { name: 'OAuth2Strategy', file: 'adapters/outbound/auth/oauth2_strategy.py', role: 'Full OAuth2/PKCE/DCR flow: initiate, complete, refresh, recovery', calls: ['HttpxAuthClient', 'FlowStateStore', 'OAuthStateManager'], calledBy: ['AuthStrategyRegistry'] },
        { name: 'ApiKeyStrategy', file: 'adapters/outbound/auth/api_key_strategy.py', role: 'API key collection strategy', calls: [], calledBy: ['AuthStrategyRegistry'] },
        { name: 'ElementValidationService', file: 'lib/mas/validation/service.py', role: 'Validates element configs (connectivity, credentials, deps) via per-spec validators', calls: ['ElementValidator', 'ElementRegistry'], calledBy: ['BlueprintService', 'ResourcesService'] },
      ]
    },
    {
      name: 'Identity & Collaboration',
      classes: [
        { name: 'Identity', file: 'lib/mas/core/identity/models.py', role: 'Identity value object: type (user|team), id, display_name. Pervasive across all persisted entities.', calls: [], calledBy: ['BlueprintService', 'SessionService', 'ResourcesService', 'ShareService', 'CollaborationService'] },
        { name: 'IdentityProvider (ABC)', file: 'lib/mas/core/identity/ports.py', role: 'Port: is_member, get_team_ids, resolve_team_id, resolve_team_display_name', calls: [], calledBy: ['IdentityPodProvider', 'DevIdentityProvider', 'CollaborationService', 'ShareService'] },
        { name: 'IdentityPodProvider', file: 'adapters/outbound/identity/identity_pod_provider.py', role: 'HTTP adapter: calls Identity service for membership/resolution', calls: ['IdentityDirectoryClient'], calledBy: ['AppContainer'] },
        { name: 'DevIdentityProvider', file: 'adapters/outbound/identity/dev_provider.py', role: 'Dev stub: permits all membership checks, no auth required', calls: [], calledBy: ['AppContainer'] },
        { name: 'CollaborationService', file: 'lib/mas/collaboration/service.py', role: 'Session presence, edit locks, typing indicators. Checks session access + team membership.', calls: ['CollaborationStore', 'SessionRepository', 'IdentityProvider'], calledBy: ['HTTP: /collaboration/'] },
        { name: 'CollaborationStore (ABC)', file: 'lib/mas/collaboration/ports.py', role: 'Port: participants, team_sessions, typing, edit locks, health', calls: [], calledBy: ['RedisCollaborationStore'] },
      ]
    },
    {
      name: 'Sharing, Templates & Statistics',
      classes: [
        { name: 'ShareService', file: 'lib/mas/sharing/service.py', role: 'Create/accept/decline invites, share_to_team. Invite-based with deep resource/blueprint cloning.', calls: ['ShareCloner', 'ShareRepository', 'IdentityProvider'], calledBy: ['HTTP: /shares/'] },
        { name: 'ShareCloner', file: 'lib/mas/sharing/cloner.py', role: 'Deep-copies resource graphs + blueprints into target identity with RID remapping', calls: ['ResourcesService', 'BlueprintService'], calledBy: ['ShareService'] },
        { name: 'TemplateService', file: 'lib/mas/templates/service.py', role: 'CRUD + instantiate (preview) + materialize (saves blueprint + resources in one step)', calls: ['TemplateRepository', 'TemplateInstantiator', 'ResourceMaterializer', 'BlueprintService', 'ElementRegistry'], calledBy: ['HTTP: /templates/'] },
        { name: 'TemplateInstantiator', file: 'lib/mas/templates/instantiation/instantiator.py', role: 'Placeholder substitution engine: fills template draft with user inputs', calls: ['PlaceholderAnalyzer'], calledBy: ['TemplateService'] },
        { name: 'ResourceMaterializer', file: 'lib/mas/templates/instantiation/resource_materializer.py', role: 'Creates actual resources from template placeholder values during materialize', calls: ['ResourcesService'], calledBy: ['TemplateService'] },
        { name: 'StatisticsService', file: 'lib/mas/statistics/service.py', role: 'Facade: user stats + admin system analytics. No own persistence.', calls: ['BlueprintService', 'SessionService', 'ResourcesService'], calledBy: ['HTTP: /statistics/'] },
        { name: 'ActionsService', file: 'lib/mas/actions/service.py', role: 'Auto-discover + execute action plugins (auth, MCP validate, tool discovery)', calls: ['BaseAction', 'ElementRegistry'], calledBy: ['HTTP: /actions/'] },
      ]
    },
    {
      name: 'Inbound Adapters — Temporal',
      classes: [
        { name: 'SessionWorkflow', file: 'adapters/inbound/temporal/workflows/session_workflow.py', role: 'Parent workflow: begin → graph traversal → complete/fail lifecycle', calls: ['BackgroundSessionRunner', 'GraphTraversalWorkflow', 'SessionLifecycleActivities'], calledBy: ['Temporal: dispatch'] },
        { name: 'GraphTraversalWorkflow', file: 'adapters/inbound/temporal/workflows/graph_traversal_workflow.py', role: 'Child workflow: BSP supersteps — plan, execute nodes, evaluate conditions, merge, repeat', calls: ['GraphTraversal', 'GraphNodeActivities'], calledBy: ['SessionWorkflow'] },
        { name: 'GraphNodeActivities', file: 'adapters/inbound/temporal/activities/graph_node_activities.py', role: 'Activity bundle: execute_graph_node (15min timeout, heartbeats) and evaluate_condition', calls: ['NodeExecutor', 'ChannelFactory'], calledBy: ['GraphTraversalWorkflow'] },
        { name: 'SessionLifecycleActivities', file: 'adapters/inbound/temporal/activities/session_lifecycle_activities.py', role: 'Activity bundle: begin/complete/fail session transitions', calls: ['BackgroundLifecycleHandler'], calledBy: ['SessionWorkflow'] },
      ]
    },
    {
      name: 'Outbound Adapters — MongoDB',
      classes: [
        { name: 'MongoBlueprintRepository', file: 'adapters/outbound/mongo/blueprint_repository.py', role: 'Blueprint persistence: blueprints collection. Indexes: blueprint_id (unique), rid_refs, identity+updated_at.', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoSessionRepository', file: 'adapters/outbound/mongo/session_repository.py', role: 'Session persistence: workflow_sessions. System analytics via $facet/$dateTrunc aggregations.', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoResourceRepository', file: 'adapters/outbound/mongo/resource_repository.py', role: 'Resource persistence: resources. Unique index on identity+category+type+name.', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoShareRepository', file: 'adapters/outbound/mongo/share_repository.py', role: 'Share invites: shares collection. TTL auto-expiry on expires_at.', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoTemplateRepository', file: 'adapters/outbound/mongo/template_repository.py', role: 'Template persistence: templates. Text search index on name+description.', calls: ['pymongo'], calledBy: ['AppContainer'] },
        { name: 'MongoCredentialStore', file: 'adapters/outbound/mongo/credential_store.py', role: 'Credential persistence: credentials. Fernet-encrypted access/refresh tokens.', calls: ['pymongo', 'cryptography.fernet'], calledBy: ['AppContainer'] },
        { name: 'MongoServerConfigStore', file: 'adapters/outbound/mongo/server_config_store.py', role: 'OAuth client configs: server_configs. Unique on server_identifier.', calls: ['pymongo'], calledBy: ['AppContainer'] },
      ]
    },
    {
      name: 'Outbound Adapters — Redis, Engine, Identity',
      classes: [
        { name: 'RedisChannelFactory', file: 'adapters/outbound/channels/redis/factory.py', role: 'Creates Redis Stream-backed session channels for distributed streaming', calls: ['redis'], calledBy: ['AppContainer'] },
        { name: 'LocalChannelFactory', file: 'adapters/outbound/channels/local/factory.py', role: 'In-process channel factory (no Redis fallback)', calls: [], calledBy: ['AppContainer'] },
        { name: 'RedisCollaborationStore', file: 'adapters/outbound/redis/collaboration_store.py', role: 'Redis-backed presence, typing, team sessions, edit locks. Keys: mas:collab:*', calls: ['redis'], calledBy: ['AppContainer'] },
        { name: 'RedisFlowStateStore', file: 'adapters/outbound/redis/flow_state_store.py', role: 'Pending OAuth flow state. Keys: auth_pending:<state_hash>. Encrypted.', calls: ['redis'], calledBy: ['AppContainer'] },
        { name: 'TemporalSessionEngine', file: 'adapters/outbound/temporal/session_engine.py', role: 'Submits SessionWorkflow to Temporal. Implements BackgroundSessionEngine port. Default execution path.', calls: ['temporalio'], calledBy: ['AppContainer'] },
        { name: 'LangGraphBuilder', file: 'adapters/outbound/langgraph/builder.py', role: 'Wraps langgraph.StateGraph with node callables from RTGraphPlan (fallback engine)', calls: ['langgraph'], calledBy: ['GraphBuilderFactory'] },
        { name: 'IdentityDirectoryClient', file: 'adapters/outbound/identity_directory_client.py', role: 'HTTP client to Identity service for user/group directory lookups', calls: ['global_utils:IdentityClient'], calledBy: ['IdentityPodProvider', 'ShareService'] },
      ]
    },
    {
      name: 'Elements Plugin Layer',
      classes: [
        { name: 'BaseElementSpec (ABC)', file: 'lib/mas/elements/common/base_element_spec.py', role: 'Declares category, type_key, config schema, factory_cls, reads/writes channels, validator_cls, card_builder_cls', calls: [], calledBy: ['* element specs (nodes, llms, tools, providers, conditions, retrievers, auths)'] },
        { name: 'BaseFactory (ABC)', file: 'lib/mas/elements/common/base_factory.py', role: 'accepts(cfg)/create(cfg, **deps) contract for all element plugins', calls: [], calledBy: ['* element factories (nodes, llms, tools, providers, conditions, retrievers, auths)'] },
        { name: 'BaseNode', file: 'lib/mas/elements/nodes/common/base_node.py', role: 'Wraps GraphState in permission-scoped StateView, calls run(). Channels via MRO.', calls: ['StateView'], calledBy: ['CustomAgentNode', 'OrchestratorNode', 'A2AAgentNode', 'ClaudeAgentNode', 'DeepAgentNode', 'UserQuestionNode', 'FinalAnswerNode', 'MergerNode', 'BranchChooserNode'] },
        { name: 'BaseTool (ABC)', file: 'lib/mas/elements/tools/common/base_tool.py', role: 'Base for tool integrations (mcp_proxy, ssh_exec, web_fetch, oc_exec)', calls: [], calledBy: ['McpProxyTool', 'WebFetchTool', 'SshExecTool', 'OcExecTool'] },
        { name: 'BaseLLM', file: 'lib/mas/elements/llms/common/base_llm.py', role: 'Base for LLM integrations (openai, google_genai, mock)', calls: [], calledBy: ['OpenAILLM', 'GoogleGenAILLM', 'MockLLM'] },
        { name: 'BaseRetriever', file: 'lib/mas/elements/retrievers/common/base_retriever.py', role: 'Base for retriever integrations (docs_rag, slack)', calls: [], calledBy: ['DocsRagRetriever', 'SlackRetriever'] },
        { name: 'McpProvider', file: 'lib/mas/elements/providers/mcp/runtime/mcp_provider.py', role: 'MCP server client: discovers tools, creates McpProxyTool instances. SSE/HTTP transport. Live auth.', calls: ['McpServerClient', 'TransportFactory', 'AuthCredential'], calledBy: ['ProviderBuilder'] },
        { name: 'ClaudeAgentNode', file: 'lib/mas/elements/nodes/claude_agent/claude_agent_node.py', role: 'Autonomous Claude SDK sessions via Vertex AI. Session-scoped working dirs, skills repos, streaming.', calls: ['claude_agent_sdk', 'IEMCapableMixin', 'WorkloadCapableMixin', 'RetrieverCapableMixin'], calledBy: ['BaseNode', 'NodeExecutor'] },
        { name: 'DeepAgentNode', file: 'lib/mas/elements/nodes/deep_agent/deep_agent_node.py', role: 'LangChain Deep Agents with planning, subagent delegation, and LocalShellBackend.', calls: ['deepagents', 'BaseLLMChatModelAdapter', 'LangChainToolsConverter', 'IEMCapableMixin', 'WorkloadCapableMixin'], calledBy: ['BaseNode', 'NodeExecutor'] },
        { name: 'BaseLLMChatModelAdapter', file: 'lib/mas/elements/llms/common/langchain_adapter.py', role: 'Bridges domain BaseLLM to LangChain BaseChatModel for DeepAgentNode', calls: ['BaseLLM'], calledBy: ['DeepAgentNode'] },
        { name: 'LangChainToolsConverter', file: 'lib/mas/elements/tools/common/converter.py', role: 'Converts domain BaseTool + MCP tools to LangChain StructuredTool format', calls: ['BaseTool', 'McpProvider'], calledBy: ['DeepAgentNode'] },
        { name: 'AgentStrategy (ABC)', file: 'lib/mas/elements/nodes/common/agent/strategies/', role: 'Base agent execution strategy (ReAct, PlanAndExecute)', calls: [], calledBy: ['AgentRunner'] },
        { name: 'AgentRunner', file: 'lib/mas/elements/nodes/common/agent/runner.py', role: 'Executes agent loop: iterate actions until finish. Uses ToolExecutorManager.', calls: ['AgentStrategy', 'AgentActionExecutor', 'ToolExecutorManager'], calledBy: ['CustomAgentNode', 'OrchestratorNode'] },
        { name: 'BuiltinTools', file: 'lib/mas/elements/tools/builtin/', role: 'Runtime-only tools (not catalog entries): workplan, topology, delegation, workspace, time, retriever-as-tool', calls: [], calledBy: ['CustomAgentNode', 'OrchestratorNode'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'http', label: 'Flask HTTP', x: 20, y: 15, w: 110, h: 34, color: '#BB86FC' },
      { id: 'session_svc', label: 'SessionService', x: 200, y: 15, w: 140, h: 34, color: '#BB86FC' },
      { id: 'factory', label: 'SessionFactory', x: 200, y: 68, w: 140, h: 34, color: '#BB86FC' },
      { id: 'runner', label: 'FgRunner', x: 200, y: 121, w: 110, h: 34, color: '#BB86FC' },
      { id: 'engine', label: 'GraphBuilder', x: 415, y: 15, w: 125, h: 34, color: '#38BDF8' },
      { id: 'elements', label: 'Elements', x: 415, y: 68, w: 110, h: 34, color: '#F472B6' },
      { id: 'mongo', label: 'Mongo (7)', x: 415, y: 121, w: 120, h: 34, color: '#86EFAC' },
      { id: 'channels', label: 'Channels', x: 415, y: 174, w: 110, h: 34, color: '#86EFAC' },
      { id: 'temporal', label: 'Temporal WF', x: 20, y: 121, w: 125, h: 34, color: '#38BDF8' },
      { id: 'iem', label: 'IEM', x: 200, y: 174, w: 80, h: 34, color: '#F472B6' },
    ],
    edges: [
        { from: 'http', to: 'session_svc', label: 'submit' },
        { from: 'session_svc', to: 'factory', label: 'build' },
        { from: 'session_svc', to: 'runner', label: 'run/submit' },
      { from: 'factory', to: 'engine', label: 'compile' },
      { from: 'factory', to: 'elements', label: 'instantiate' },
      { from: 'runner', to: 'channels', label: 'stream' },
      { from: 'runner', to: 'mongo', label: 'persist' },
      { from: 'temporal', to: 'factory', label: 'rebuild' },
      { from: 'elements', to: 'iem', label: 'packets' },
    ],
  },
};
