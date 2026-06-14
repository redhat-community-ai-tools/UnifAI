---
service: ui
type: APP
code_root: ui/
sections:
  connections: 26
  features: 37
  job_description: 46
  endpoints_72: 110
  architecture: 239
  class_architecture: 310
---

# UI / Nginx

> React SPA + reverse proxy

| Field | Value |
|-------|-------|
| ID | `ui` |
| Type | APP |
| Tech Stack | React 18, TypeScript, Vite, Nginx, Tailwind CSS, shadcn/ui, TanStack Query, Wouter, JointJS |
| Code Root | `ui/` |
| Subtitle | React 18 + TypeScript + Vite • Nginx reverse proxy |

## Connections

**Incoming:**
- `browser` → `ui` *(HTTP)*

**Outgoing:**
- `ui` → `rag` *(/api1)*
- `ui` → `mas` *(/api2)*
- `ui` → `identity` *(/api3)*
- `ui` → `platform` *(/api4)*

## Features

- **Chats (Sessions)** — Execute blueprints & stream responses
- **Agentic AI Inventory** — Browse & configure AI building blocks
- **Overview Dashboards** — Stats & monitoring for RAG and Agentic AI
- **RAG Data Pipeline** — Ingest documents & search semantically
- **Team Workspace** — Shared team identity & real-time collaboration
- **Agentic AI Workflows** — Build & manage blueprint graphs

## Job Description

The **UI** is the single entry point for all browser traffic. It's a React 18 SPA (~280 TypeScript files) that provides the blueprint builder, real-time agent chat, RAG dashboard, team collaboration, template catalog, and admin configuration panel.

In production, **Nginx** serves static assets and reverse-proxies API requests to 4 backend services based on URL path prefix.

#### Key Features

- **Visual Graph Builder** — JointJS canvas for building agent workflows with drag-and-drop nodes, edges, and conditions. YAML-backed, with dagre auto-layout on load.
- **Real-Time Agent Chat** — NDJSON streaming from MAS via Redis Streams. Live graph node status overlays. Multi-session hub.
- **Team Collaboration** — Shared workspaces with real-time presence, typing indicators, edit locks, and session busy-state.
- **RAG Dashboard** — Document upload, Slack channel management, pipeline monitoring, chunk analytics.
- **Template Marketplace** — Browse, preview, and materialize parameterized blueprint templates into ready-to-use workflows.
- **Sharing System** — Share blueprints and resources between users/teams with invitation-based cloning and notification panel.
- **Agent Inventory** — CRUD for all resource types (LLMs, tools, providers, retrievers, conditions, nodes, auths) with schema-driven dynamic forms.
- **Admin Config** — Template-driven admin settings page (admin gated via Platform Backend).

#### Nginx Path Routing

- `/api1/*` → RAG (port 13457)
- `/api2/*` → Multi Agent System (MAS) (port 8002) — streaming endpoints get 600s timeout + `proxy_buffering off`
- `/api3/*` → Identity (307 redirect to external host)
- `/api4/*` → Platform Backend (port 8005)

#### Application Routes (15+)

- **Agentic Routes** (AgenticLayout + team gating):

- `/agentic-overview` — dashboard: stats, workflow list, resource charts
- `/agentic-ai` — graph builder + execution preview
- `/inventory` — resource CRUD (workspace elements)
- `/agentic-chats` — personal ExecutionTab or team CollaborationHubView
- `/templates` — template catalog → materialize → session

- **RAG Routes**:

- `/rag-overview` — RAG dashboard with pipeline polling
- `/documents` — document upload/embed pipeline
- `/slack` + `/slack/add-source` — Slack channel management

- **Other**: `/` (Get to Know), `/login`, `/configuration` (admin), `/analytics` (system stats), `/guides`, `/jira`
- **Public**: `/chat/:token` — public blueprint chat (no auth required)

#### Session Streaming Architecture

- **1.** `POST /sessions/user.session.submit` → 202 with workflow ID
- **2.** `fetch(/api2/sessions/session.subscribe)` → NDJSON stream via `ReadableStream`
- **3.** `useSessionStream` hook parses line-delimited JSON with reconnect logic
- **4.** `StreamingDataContext` holds `Map<nodeId, NodeEntry>` for live graph overlays
- **5.** `ChatInterface` renders LLM tokens, tool calls, node transitions in real-time

#### Workspace Identity Pattern

`useWorkspaceIdentity()` is the single source of truth for `userId`, `identityType` (user vs team), and `displayName`. It feeds API params for every identity-scoped call. Backed by `AuthContext` (session) + `ViewContext` (team switching).

#### Graph Builder

Built on **JointJS** (`@joint/core` + `@joint/layout-directed-graph` + dagre). Two modes:

- **Creation** (`useGraphCreationLogic` + `useGraphCreationCanvas`) — canvas editing, YAML serialization via `js-yaml`, draft validation, save/update blueprint.
- **Display** (`useGraphDisplay`) — read-only graph with live status overlays from StreamingDataContext.

Team mode adds **edit locks** — only one user can edit a blueprint at a time.

## Endpoints (72)

### Sessions — /api2

| Method | Path | Summary |
|--------|------|--------|
| POST | `/sessions/user.session.create` |  |
| POST | `/sessions/user.session.submit` | trigger execution |
| POST | `/sessions/session.cancel` |  |
| GET | `/sessions/session.stream.status` |  |
| GET | `/sessions/session.subscribe` | NDJSON stream (raw fetch) |
| GET | `/sessions/session.user.list` |  |
| GET | `/sessions/session.chat.get` |  |
| DEL | `/sessions/session.delete` |  |

### Blueprints — /api2

| Method | Path | Summary |
|--------|------|--------|
| GET | `/blueprints/available.blueprints.get` |  |
| GET | `/blueprints/available.blueprints.summary.get` |  |
| GET | `/blueprints/available.blueprints.resolved.get` |  |
| GET | `/blueprints/blueprint.info.get` |  |
| POST | `/blueprints/blueprint.save` |  |
| PUT | `/blueprints/blueprint.update` |  |
| PUT | `/blueprints/blueprint.metadata.set` |  |
| POST | `/blueprints/blueprint.validate` |  |
| POST | `/blueprints/draft.validate` |  |
| DEL | `/blueprints/remove.blueprint` |  |

### Resources & Catalog — /api2

| Method | Path | Summary |
|--------|------|--------|
| GET | `/resources/resources.list` | filtered by category |
| POST | `/resources/resource.save` |  |
| PUT | `/resources/resource.update` |  |
| DEL | `/resources/resource.delete` |  |
| POST | `/resources/resource.validate` |  |
| GET | `/catalog/elements.list.get` |  |
| GET | `/catalog/categories.list.get` |  |
| POST | `/actions/action.execute` |  |

### Templates — /api2

| Method | Path | Summary |
|--------|------|--------|
| GET | `/templates/templates.list` |  |
| GET | `/templates/template.get` |  |
| GET | `/templates/template.schema.get` |  |
| POST | `/templates/template.input.validate` |  |
| POST | `/templates/template.materialize` |  |

### Shares & Collaboration — /api2

| Method | Path | Summary |
|--------|------|--------|
| POST | `/shares/share.create` |  |
| GET | `/shares/shares.list` |  |
| POST | `/shares/share.accept / share.decline / share.to_team` |  |
| POST | `/collaboration/session.join / session.leave / session.heartbeat` |  |
| GET | `/collaboration/session.participants` |  |
| POST | `/collaboration/session.typing` |  |
| POST | `/collaboration/edit_lock.acquire / release / heartbeat` |  |
| POST | `/collaboration/edit_lock.statuses` | batch status check |

### Statistics — /api2

| Method | Path | Summary |
|--------|------|--------|
| GET | `/statistics/stats.get` | user dashboard |
| GET | `/statistics/stats.system.get` | admin analytics |
| GET | `/sessions/session.user.blueprints.get` |  |

### Graph Validation — /api2

| Method | Path | Summary |
|--------|------|--------|
| POST | `/graph/validation/all.validate` | full topology check |

### Auth & Teams — /api3

| Method | Path | Summary |
|--------|------|--------|
| GET | `/auth/user` | current session user |
| GET | `/auth/user/groups` | LDAP groups |
| POST | `/auth/logout` |  |
| POST | `/auth/refresh` |  |
| POST | `/teams/team.create` |  |
| GET | `/teams/teams.list / team.get` |  |
| PUT | `/teams/team.update` |  |
| DEL | `/teams/team.delete + /workspace/workspace.cleanup` |  |

### Directory — /api3

| Method | Path | Summary |
|--------|------|--------|
| GET | `/directory/directory.status` |  |
| GET | `/directory/directory.search_users` |  |
| GET | `/directory/directory.search` | users + groups |
| GET | `/directory/directory.get_group` |  |

### RAG — /api1

| Method | Path | Summary |
|--------|------|--------|
| GET | `/data_sources/data.sources.get` |  |
| GET | `/data_sources/data.source.details.get` |  |
| POST | `/docs/upload` | multipart file upload |
| POST | `/docs/validate` |  |
| PUT | `/pipelines/embed` |  |
| DEL | `/data_sources/data.source.delete` |  |
| GET | `/docs/supported-extensions` |  |
| GET | `/slack/available.slack.channels.get` |  |
| GET | `/vector/chunks.counts` |  |
| GET | `/health/service.readiness.get` |  |

### Admin Config — /api4

| Method | Path | Summary |
|--------|------|--------|
| GET | `/admin_config/config.get` |  |
| PUT | `/admin_config/config.section.update` |  |
| GET | `/admin_config/access.check` |  |
| PROXY | `/api1/ → RAG_IP:RAG_PORT/api/` |  |
| PROXY | `/api2/ → MULTIAGENT_IP:MULTIAGENT_PORT/api/` |  |
| 307 | `/api3/* → IDENTITY_HOST/api/*` |  |
| PROXY | `/api4/ → BACKEND_IP:BACKEND_PORT/api/` |  |

## Architecture

#### Tech Stack

- **Core**: React 18, TypeScript, Vite
- **Styling**: Tailwind CSS + shadcn/ui (51 Radix-based primitives in `components/ui/`)
- **Routing**: Wouter (lightweight client router)
- **Server State**: TanStack React Query v5
- **Graph Canvas**: JointJS (`@joint/core` + dagre layout). *Note: react-flow-renderer in deps but fully migrated to JointJS.*
- **Forms**: react-hook-form + zod validation
- **Charts**: Recharts (analytics, resource distribution)
- **Streaming**: Native `fetch` + `ReadableStream` for NDJSON, oboe for JSON parsing
- **Animations**: Framer Motion
- **Markdown**: react-markdown + remark-gfm (chat rendering)

#### Source Layout (~280 TS/TSX files)

- `api/` (19 files) — typed API modules, one per domain
- `components/` (162 files) — `agentic-ai/` (51), `ui/` (51 shadcn), `shared/` (22), `analytics/` (11), `dashboard/` (10), `layout/` (4), `auth/` (4)
- `hooks/` (23 files) — domain-specific custom hooks
- `contexts/` (7 files) — 8 app-level React context providers
- `http/` (4 files) — axios client instances + React Query client
- `features/` (22 files) — feature slices (slack, docs, configuration)
- `pages/` (12 files) — route-level page components
- `types/` (8 files) — shared TypeScript types (graph, session, workspace, templates, validation)
- `stores/` (1 file) — Zustand pagination store (currently unused)

#### Context Provider Tree

The app wraps routes in a nested provider hierarchy:

- `QueryClientProvider` → `ThemeProvider` → `AuthProvider` → `SharedProvider` → `ViewProvider` → `ProjectProvider` → `NotificationProvider` → routes
- Route-scoped: `AgenticAIProvider` (agentic routes), `StreamingDataProvider` (chat/execution views)

| Context | Hook | Responsibility |
|---|---|---|
| AuthContext | `useAuth` | User session, login/logout, token refresh, sets `X-Authenticated-User` |
| ViewContext | `useView` | Private vs team workspace, selected team, user groups |
| ThemeContext | `useTheme` | Dark/light toggle, primary color CSS vars (localStorage) |
| SharedContext | `useShared` | Share panel open/close, item being shared |
| NotificationContext | `useNotifications` | Share invites (received/sent), accept/decline |
| AgenticAIContext | `useAgenticAI` | Resource UUID↔name maps, validation caches, dependency revalidation (~760 LOC) |
| StreamingDataContext | `useStreamingData` | In-memory node stream map for live graph/chat updates |
| ProjectContext | `useProject` | Legacy mock/sample project data for dashboard |

#### Custom Hooks (23)

| Hook | Domain | Summary |
|---|---|---|
| `useWorkspaceIdentity` | Identity | Single source of truth for userId, identityType, displayName |
| `useSessionStream` | Streaming | NDJSON Redis stream: submit → subscribe → reconnect |
| `useSessionHub` | Sessions | Shared session list/CRUD/execution for ExecutionTab |
| `useGraphCreationLogic` | Graph | Canvas state, YAML, validation, save/update (~1471 LOC) |
| `useGraphCreationCanvas` | Graph | JointJS paper sync for creation canvas |
| `useGraphDisplay` | Graph | Read-only JointJS + live status overlays |
| `useLoadBlueprint` | Blueprints | Load spec → canvas nodes/edges with dagre layout |
| `useTemplates` | Templates | List, detail, schema, validate, materialize |
| `useWorkspaceData` | Inventory | Category-based element CRUD |
| `useTeamEditLockPoll` | Collaboration | Poll edit lock statuses for team resources |

#### State Management

- **React Context** — primary global state (auth, workspace, agentic mappings, notifications, streaming)
- **TanStack React Query v5** — server state for all API calls (RAG dashboard, MAS resources, admin config, analytics)
- **Local useState/useRef** — heavy use in graph builder, chat, collaboration hub
- **localStorage** — theme, primary color

#### Dynamic Field System

Agent inventory forms are schema-driven: `FieldRenderer`, `FieldValidation`, `FieldPopulation`, and `AuthFieldRenderer` call backend via registered actions (`/actions/action.execute`) and schema-driven `ApiHint` endpoints.

## Class Architecture

The UI is a React 18 SPA (~280 TS/TSX files) with Nginx reverse proxy. Architecture: page routes → feature components → hooks → typed API modules → 4 axios clients → Nginx → backends. State flows through 8 React Contexts + TanStack Query.

### Key Extension Points

These are the base classes and ABCs that new code should extend or implement:

| Class | File | Layer | Implementations / Subclasses |
|-------|------|-------|------------------------------|
| `shadcn/ui (51 components)` | `components/ui/` | Shared UI Components | `all components` |

### API Clients & HTTP

| Class | File | Role |
|-------|------|------|
| `queryClient` | `http/query-config.ts` | Axios instance for RAG (baseURL: /api1). All RAG calls route through this. |
| `axiosAgentConfig` | `http/agent-config.ts` | Axios instance for MAS (baseURL: /api2). X-Authenticated-User header injected. |
| `authClient` | `http/auth-config.ts` | Axios instance for Identity (baseURL: /api3, withCredentials: true) |
| `backendClient` | `http/backend-config.ts` | Axios instance for Platform (baseURL: /api4) |
| `reactQueryClient` | `http/react-query-client.ts` | TanStack QueryClient (5m staleTime, 10m gcTime defaults) |

- `queryClient` calls: `axios`
- `queryClient` called by: `api/data-sources.ts`, `api/docs.ts`, `api/slack.ts`, `api/pipelines.ts`
- `axiosAgentConfig` calls: `axios`
- `axiosAgentConfig` called by: `api/sessions.ts`, `api/blueprints.ts`, `api/resources.ts`, `api/templates.ts`, `api/shares.ts`
- `authClient` calls: `axios`
- `authClient` called by: `api/auth.ts`, `api/teams.ts`, `api/directory.ts`

### Context Providers

| Class | File | Role |
|-------|------|------|
| `AuthProvider` | `contexts/AuthContext.tsx` | Session lifecycle: login redirect → cookie → /auth/user → refresh loop |
| `ViewProvider` | `contexts/ViewContext.tsx` | Private/team workspace switch, team selection, LDAP groups |
| `ThemeProvider` | `contexts/ThemeContext.tsx` | Dark/light toggle + primary color CSS custom props (localStorage) |
| `SharedProvider` | `contexts/SharedContext.tsx` | Share dialog state: what item is being shared, panel open/close |
| `NotificationProvider` | `contexts/NotificationContext.tsx` | Share invite polling: received/sent invites, accept/decline flows |
| `AgenticAIProvider` | `contexts/AgenticAIContext.tsx` | Resource UUID↔name maps, validation caches, dependency revalidation. ~760 LOC. |
| `StreamingDataProvider` | `contexts/StreamingDataContext.tsx` | In-memory Map<nodeId, NodeEntry> holding live stream data for graph overlays |
| `ProjectProvider` | `contexts/ProjectContext.tsx` | Legacy mock/sample project data for dashboard cards |

- `AuthProvider` calls: `authClient`, `HTTP: /auth/user`, `HTTP: /auth/refresh`
- `AuthProvider` called by: `App.tsx`
- `AgenticAIProvider` calls: `api/resources`, `api/catalog`, `api/blueprints`
- `AgenticAIProvider` called by: `AgenticLayout`

### Custom Hooks — Graph

| Class | File | Role |
|-------|------|------|
| `useGraphCreationLogic` | `hooks/use-graph-creation-logic.ts` | Canvas state machine: add/remove nodes, YAML serialization, draft validation, save/update. ~1471 LOC. |
| `useGraphCreationCanvas` | `hooks/use-graph-creation-canvas.ts` | JointJS paper lifecycle: init graph, sync nodes/edges to canvas, handle clicks |
| `useGraphDisplay` | `hooks/use-graph-display.ts` | Read-only JointJS paper with live status overlays from StreamingDataContext |
| `useLoadBlueprint` | `hooks/use-load-blueprint.ts` | Load blueprint spec → JointJS nodes/edges with dagre auto-layout |

- `useGraphCreationLogic` calls: `useAgenticAI`, `api/blueprints`, `js-yaml`
- `useGraphCreationLogic` called by: `NewGraph`, `EditGraph`

### Custom Hooks — Sessions & Streaming

| Class | File | Role |
|-------|------|------|
| `useSessionStream` | `hooks/use-session-stream.ts` | NDJSON stream: fetch(session.subscribe) → ReadableStream → parse line-delimited JSON → reconnect |
| `useSessionHub` | `hooks/use-session-hub.ts` | Shared session CRUD + execution lifecycle for ExecutionTab |
| `useWorkspaceIdentity` | `hooks/use-workspace-identity.ts` | Single source of truth: userId, identityType (user\|team), displayName |
| `useTemplates` | `hooks/use-templates.ts` | Template lifecycle: list → detail → schema → validate → materialize |

- `useWorkspaceIdentity` calls: `useAuth`, `useView`
- `useWorkspaceIdentity` called by: `useSessionHub`, `useWorkspaceData`, `useGraphCreationLogic`

### Custom Hooks — Collaboration & Data

| Class | File | Role |
|-------|------|------|
| `useTeamEditLockPoll` | `hooks/use-team-edit-lock-poll.ts` | Periodic poll of edit lock statuses for team blueprint list |
| `useWorkspaceData` | `hooks/use-workspace-data.ts` | Category-based element CRUD with TanStack Query |
| `usePipelinePolling` | `hooks/use-pipeline-polling.ts` | Polls RAG pipeline status during active ingestion |

### Page-Level Components

| Class | File | Role |
|-------|------|------|
| `AgenticOverview` | `pages/AgenticOverview.tsx` | Dashboard: workflow stats, resource distribution charts, blueprint list |
| `NewGraph` | `workspace/NewGraph.tsx` | Graph builder canvas: element palette, properties panel, YAML editor |
| `ExecutionTab / CollaborationHubView` | `components/agentic-ai/chat/` | Session list + ChatInterface. Team mode adds presence + typing indicators. |
| `TemplatesCatalog` | `components/agentic-ai/templates/` | Browse → preview → materialize parameterized templates |
| `ChatInterface` | `components/agentic-ai/chat/ChatInterface.tsx` | Real-time agent chat: LLM tokens, tool calls, node transitions. ~1582 LOC. |
| `Inventory` | `components/agentic-ai/inventory/` | CRUD for all resource categories with schema-driven FieldRenderer |

- `ExecutionTab / CollaborationHubView` calls: `useSessionHub`, `useSessionStream`, `StreamingDataProvider`
- `ExecutionTab / CollaborationHubView` called by: `Router: /agentic-chats`
- `ChatInterface` calls: `useSessionStream`, `StreamingDataContext`, `react-markdown`
- `ChatInterface` called by: `ExecutionTab`

### Shared UI Components

| Class | File | Role |
|-------|------|------|
| `shadcn/ui (51 components)` | `components/ui/` | Radix UI + Tailwind primitives: Button, Dialog, Select, Sheet, Toast, etc. |
| `FieldRenderer` | `components/shared/FieldRenderer.tsx` | Schema-driven dynamic forms: type-based rendering, API hints, validation |
| `ShareWorkflow` | `components/agentic-ai/ShareWorkflow.tsx` | Share dialog: search users/groups, create invite, copy link |
| `GraphDisplay` | `components/agentic-ai/graphs/GraphDisplay.tsx` | Read-only JointJS graph with live node status overlays |

- `FieldRenderer` calls: `api/actions`, `FieldValidation`, `FieldPopulation`
- `FieldRenderer` called by: `Inventory`, `AdminConfig`
- `ShareWorkflow` calls: `api/shares`, `api/directory`, `useShared`
- `ShareWorkflow` called by: `BlueprintList`, `ResourceList`

### Nginx Deployment

| Class | File | Role |
|-------|------|------|
| `nginx.conf.template` | `deployment/nginx.conf.template` | Reverse proxy config: /api1→RAG, /api2→MAS (streaming), /api3→Identity (307), /api4→Platform |

---

*Source: `js/data/services/ui.js`* | *Classes: `js/data-classes/ui.js`*
