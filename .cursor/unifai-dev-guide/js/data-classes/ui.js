SERVICE_CLASSES.ui = {
  description: `<p>The UI is a React 18 SPA (~280 TS/TSX files) with Nginx reverse proxy. Architecture: page routes → feature components → hooks → typed API modules → 4 axios clients → Nginx → backends. State flows through 8 React Contexts + TanStack Query.</p>`,
  layers: [
    {
      name: 'API Clients & HTTP',
      classes: [
        { name: 'queryClient', file: 'http/query-config.ts', role: 'Axios instance for RAG (baseURL: /api1). All RAG calls route through this.', calls: ['axios'], calledBy: ['api/data-sources.ts', 'api/docs.ts', 'api/slack.ts', 'api/pipelines.ts'] },
        { name: 'axiosAgentConfig', file: 'http/agent-config.ts', role: 'Axios instance for MAS (baseURL: /api2). X-Authenticated-User header injected.', calls: ['axios'], calledBy: ['api/sessions.ts', 'api/blueprints.ts', 'api/resources.ts', 'api/templates.ts', 'api/shares.ts'] },
        { name: 'authClient', file: 'http/auth-config.ts', role: 'Axios instance for Identity (baseURL: /api3, withCredentials: true)', calls: ['axios'], calledBy: ['api/auth.ts', 'api/teams.ts', 'api/directory.ts'] },
        { name: 'backendClient', file: 'http/backend-config.ts', role: 'Axios instance for Platform (baseURL: /api4)', calls: ['axios'], calledBy: ['api/admin-config.ts'] },
        { name: 'reactQueryClient', file: 'http/react-query-client.ts', role: 'TanStack QueryClient (5m staleTime, 10m gcTime defaults)', calls: ['@tanstack/react-query'], calledBy: ['App.tsx'] },
      ]
    },
    {
      name: 'Context Providers',
      classes: [
        { name: 'AuthProvider', file: 'contexts/AuthContext.tsx', role: 'Session lifecycle: login redirect → cookie → /auth/user → refresh loop', calls: ['authClient', 'HTTP: /auth/user', 'HTTP: /auth/refresh'], calledBy: ['App.tsx'] },
        { name: 'ViewProvider', file: 'contexts/ViewContext.tsx', role: 'Private/team workspace switch, team selection, LDAP groups', calls: ['useAuth', 'api/teams'], calledBy: ['App.tsx'] },
        { name: 'ThemeProvider', file: 'contexts/ThemeContext.tsx', role: 'Dark/light toggle + primary color CSS custom props (localStorage)', calls: [], calledBy: ['App.tsx'] },
        { name: 'SharedProvider', file: 'contexts/SharedContext.tsx', role: 'Share dialog state: what item is being shared, panel open/close', calls: [], calledBy: ['App.tsx'] },
        { name: 'NotificationProvider', file: 'contexts/NotificationContext.tsx', role: 'Share invite polling: received/sent invites, accept/decline flows', calls: ['api/shares'], calledBy: ['App.tsx'] },
        { name: 'AgenticAIProvider', file: 'contexts/AgenticAIContext.tsx', role: 'Resource UUID↔name maps, validation caches, dependency revalidation. ~760 LOC.', calls: ['api/resources', 'api/catalog', 'api/blueprints'], calledBy: ['AgenticLayout'] },
        { name: 'StreamingDataProvider', file: 'contexts/StreamingDataContext.tsx', role: 'In-memory Map<nodeId, NodeEntry> holding live stream data for graph overlays', calls: [], calledBy: ['ExecutionTab', 'ChatInterface'] },
        { name: 'ProjectProvider', file: 'contexts/ProjectContext.tsx', role: 'Legacy mock/sample project data for dashboard cards', calls: [], calledBy: ['App.tsx'] },
      ]
    },
    {
      name: 'Custom Hooks — Graph',
      classes: [
        { name: 'useGraphCreationLogic', file: 'hooks/use-graph-creation-logic.ts', role: 'Canvas state machine: add/remove nodes, YAML serialization, draft validation, save/update. ~1471 LOC.', calls: ['useAgenticAI', 'api/blueprints', 'js-yaml'], calledBy: ['NewGraph', 'EditGraph'] },
        { name: 'useGraphCreationCanvas', file: 'hooks/use-graph-creation-canvas.ts', role: 'JointJS paper lifecycle: init graph, sync nodes/edges to canvas, handle clicks', calls: ['@joint/core', '@joint/layout-directed-graph'], calledBy: ['NewGraph'] },
        { name: 'useGraphDisplay', file: 'hooks/use-graph-display.ts', role: 'Read-only JointJS paper with live status overlays from StreamingDataContext', calls: ['@joint/core', 'useStreamingData'], calledBy: ['GraphDisplay'] },
        { name: 'useLoadBlueprint', file: 'hooks/use-load-blueprint.ts', role: 'Load blueprint spec → JointJS nodes/edges with dagre auto-layout', calls: ['@joint/layout-directed-graph', 'dagre'], calledBy: ['useGraphCreationLogic'] },
      ]
    },
    {
      name: 'Custom Hooks — Sessions & Streaming',
      classes: [
        { name: 'useSessionStream', file: 'hooks/use-session-stream.ts', role: 'NDJSON stream: fetch(session.subscribe) → ReadableStream → parse line-delimited JSON → reconnect', calls: ['fetch', 'StreamingDataContext'], calledBy: ['ChatInterface'] },
        { name: 'useSessionHub', file: 'hooks/use-session-hub.ts', role: 'Shared session CRUD + execution lifecycle for ExecutionTab', calls: ['api/sessions', 'useWorkspaceIdentity'], calledBy: ['ExecutionTab', 'CollaborationHubView'] },
        { name: 'useWorkspaceIdentity', file: 'hooks/use-workspace-identity.ts', role: 'Single source of truth: userId, identityType (user|team), displayName', calls: ['useAuth', 'useView'], calledBy: ['useSessionHub', 'useWorkspaceData', 'useGraphCreationLogic'] },
        { name: 'useTemplates', file: 'hooks/use-templates.ts', role: 'Template lifecycle: list → detail → schema → validate → materialize', calls: ['api/templates'], calledBy: ['TemplatesCatalog', 'TemplatePreview'] },
      ]
    },
    {
      name: 'Custom Hooks — Collaboration & Data',
      classes: [
        { name: 'useTeamEditLockPoll', file: 'hooks/use-team-edit-lock-poll.ts', role: 'Periodic poll of edit lock statuses for team blueprint list', calls: ['api/collaboration'], calledBy: ['BlueprintList'] },
        { name: 'useWorkspaceData', file: 'hooks/use-workspace-data.ts', role: 'Category-based element CRUD with TanStack Query', calls: ['api/resources', 'useAgenticAI'], calledBy: ['Inventory'] },
        { name: 'usePipelinePolling', file: 'hooks/use-pipeline-polling.ts', role: 'Polls RAG pipeline status during active ingestion', calls: ['api/pipelines', 'api/data-sources'], calledBy: ['RAGOverview'] },
      ]
    },
    {
      name: 'Page-Level Components',
      classes: [
        { name: 'AgenticOverview', file: 'pages/AgenticOverview.tsx', role: 'Dashboard: workflow stats, resource distribution charts, blueprint list', calls: ['useAgenticAI', 'api/statistics'], calledBy: ['Router: /agentic-overview'] },
        { name: 'NewGraph', file: 'workspace/NewGraph.tsx', role: 'Graph builder canvas: element palette, properties panel, YAML editor', calls: ['useGraphCreationLogic', 'useGraphCreationCanvas'], calledBy: ['Router: /agentic-ai'] },
        { name: 'ExecutionTab / CollaborationHubView', file: 'components/agentic-ai/chat/', role: 'Session list + ChatInterface. Team mode adds presence + typing indicators.', calls: ['useSessionHub', 'useSessionStream', 'StreamingDataProvider'], calledBy: ['Router: /agentic-chats'] },
        { name: 'TemplatesCatalog', file: 'components/agentic-ai/templates/', role: 'Browse → preview → materialize parameterized templates', calls: ['useTemplates', 'api/templates'], calledBy: ['Router: /templates'] },
        { name: 'ChatInterface', file: 'components/agentic-ai/chat/ChatInterface.tsx', role: 'Real-time agent chat: LLM tokens, tool calls, node transitions. ~1582 LOC.', calls: ['useSessionStream', 'StreamingDataContext', 'react-markdown'], calledBy: ['ExecutionTab'] },
        { name: 'Inventory', file: 'components/agentic-ai/inventory/', role: 'CRUD for all resource categories with schema-driven FieldRenderer', calls: ['useWorkspaceData', 'FieldRenderer'], calledBy: ['Router: /inventory'] },
      ]
    },
    {
      name: 'Shared UI Components',
      classes: [
        { name: 'shadcn/ui (51 components)', file: 'components/ui/', role: 'Radix UI + Tailwind primitives: Button, Dialog, Select, Sheet, Toast, etc.', calls: ['@radix-ui', 'class-variance-authority'], calledBy: ['* all components'] },
        { name: 'FieldRenderer', file: 'components/shared/FieldRenderer.tsx', role: 'Schema-driven dynamic forms: type-based rendering, API hints, validation', calls: ['api/actions', 'FieldValidation', 'FieldPopulation'], calledBy: ['Inventory', 'AdminConfig'] },
        { name: 'ShareWorkflow', file: 'components/agentic-ai/ShareWorkflow.tsx', role: 'Share dialog: search users/groups, create invite, copy link', calls: ['api/shares', 'api/directory', 'useShared'], calledBy: ['BlueprintList', 'ResourceList'] },
        { name: 'GraphDisplay', file: 'components/agentic-ai/graphs/GraphDisplay.tsx', role: 'Read-only JointJS graph with live node status overlays', calls: ['useGraphDisplay', 'StreamingDataContext'], calledBy: ['ChatInterface', 'AgenticOverview'] },
      ]
    },
    {
      name: 'Nginx Deployment',
      classes: [
        { name: 'nginx.conf.template', file: 'deployment/nginx.conf.template', role: 'Reverse proxy config: /api1→RAG, /api2→MAS (streaming), /api3→Identity (307), /api4→Platform', calls: [], calledBy: ['Docker: envsubst'] },
      ]
    },
  ],
  scheme: {
    nodes: [
      { id: 'pages', label: 'Pages', x: 20, y: 15, w: 85, h: 34, color: '#BB86FC' },
      { id: 'hooks', label: 'Hooks (23)', x: 20, y: 68, w: 110, h: 34, color: '#BB86FC' },
      { id: 'ctx', label: 'Contexts (8)', x: 180, y: 15, w: 120, h: 34, color: '#A78BFA' },
      { id: 'api', label: 'API (19)', x: 180, y: 68, w: 100, h: 34, color: '#BB86FC' },
      { id: 'stream', label: 'Streaming', x: 180, y: 121, w: 110, h: 34, color: '#38BDF8' },
      { id: 'axios', label: 'Axios (4)', x: 370, y: 40, w: 100, h: 34, color: '#86EFAC' },
      { id: 'nginx', label: 'Nginx', x: 370, y: 95, w: 90, h: 34, color: '#86EFAC' },
      { id: 'backends', label: 'Backends', x: 530, y: 65, w: 100, h: 34, color: '#FBBF24' },
    ],
    edges: [
      { from: 'pages', to: 'hooks', label: 'use' },
      { from: 'pages', to: 'ctx', label: 'consume' },
      { from: 'hooks', to: 'api', label: 'call' },
      { from: 'hooks', to: 'stream', label: 'NDJSON' },
      { from: 'api', to: 'axios', label: 'HTTP' },
      { from: 'stream', to: 'nginx', label: 'fetch' },
      { from: 'axios', to: 'nginx', label: 'proxy' },
      { from: 'nginx', to: 'backends', label: 'route' },
    ],
  },
};
