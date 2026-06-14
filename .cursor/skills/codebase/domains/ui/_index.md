---
name: ui-frontend
scope: React/TypeScript frontend application
parent: ../SKILL.md
when_to_load: Any work touching ui/client/src/
---

# UI Frontend

React 18 SPA (~280 TS/TSX files) with Nginx reverse proxy. Feature-oriented layout (NOT hexagonal).

## Component Routing

| Path prefix | Module | Files | Description |
|-------------|--------|-------|-------------|
| `api/` | API Layer | ~19 | Typed API modules, one per backend target service |
| `components/agentic-ai/` | Agentic AI | ~51 | Graph builder, chat, templates, inventory |
| `components/ui/` | shadcn/ui | ~51 | Radix-based UI primitives (Button, Dialog, Select, etc.) |
| `components/shared/` | Shared | ~22 | FieldRenderer, ShareWorkflow, common widgets |
| `hooks/` | Custom Hooks | ~23 | Domain hooks (sessions, graphs, workspace, etc.) |
| `contexts/` | React Contexts | 7 files / 8 contexts | Auth, Theme, View, Shared, Notification, AgenticAI, Streaming, Project |
| `http/` | HTTP Clients | 4 | Axios instances for each backend service |
| `features/` | Feature Modules | ~22 | Slack, docs, configuration slices |
| `pages/` | Pages | ~12 | Route-level page components |
| `types/` | Types | ~8 | Shared TypeScript types (graph, session, workspace, templates) |

## HTTP Clients (4 backends)

| Client | File | Base URL | Target |
|--------|------|----------|--------|
| `queryClient` | `http/queryClient.ts` | `/api1` | RAG |
| `axiosAgentConfig` | `http/axiosAgentConfig.ts` | `/api2` | MAS |
| `authClient` | `http/authClient.ts` | `/api3` | Identity |
| `backendClient` | `http/backendClient.ts` | `/api4` | Platform |

## Context Provider Tree

```
QueryClientProvider → ThemeProvider → AuthProvider → SharedProvider
  → ViewProvider → ProjectProvider → NotificationProvider → routes
      Route-scoped: AgenticAIProvider (agentic routes)
                    StreamingDataProvider (chat/execution views)
```

| Context | Hook | Key Responsibility |
|---------|------|--------------------|
| `AuthContext` | `useAuth` | Session, login/logout, token refresh, `X-Authenticated-User` |
| `ViewContext` | `useView` | Private vs team workspace, selected team, user groups |
| `ThemeContext` | `useTheme` | Dark/light toggle, primary color CSS vars |
| `AgenticAIContext` | `useAgenticAI` | Resource UUID↔name maps, validation caches (~760 LOC) |
| `StreamingDataContext` | `useStreamingData` | In-memory node stream map for live graph/chat |
| `NotificationContext` | `useNotifications` | Share invites (received/sent), accept/decline |

## Key Hooks

| Hook | Domain | Summary |
|------|--------|---------|
| `useWorkspaceIdentity` | Identity | Single source of truth for userId, identityType, displayName |
| `useSessionStream` | Streaming | NDJSON Redis stream: submit → subscribe → reconnect |
| `useSessionHub` | Sessions | Shared session list/CRUD/execution |
| `useGraphCreationLogic` | Graph | Canvas state, YAML, validation, save/update (~1471 LOC) |
| `useGraphCreationCanvas` | Graph | JointJS paper sync for creation canvas |
| `useGraphDisplay` | Graph | Read-only JointJS + live status overlays |
| `useTemplates` | Templates | List, detail, schema, validate, materialize |
| `useWorkspaceData` | Inventory | Category-based element CRUD |

## Nginx Path Routing (production)

| Path | Target | Notes |
|------|--------|-------|
| `/api1/*` | RAG (port 13457) | Standard proxy |
| `/api2/*` | MAS (port 8002) | Streaming: 600s timeout, `proxy_buffering off` |
| `/api3/*` | Identity | 307 redirect to `IDENTITY_HOST` |
| `/api4/*` | Platform (port 8005) | Standard proxy |

## Dev-Guide Facts

For full endpoint catalog (72 endpoints), component details, and hook documentation:
- **Service doc:** `unifai-dev-guide/docs/services/ui.md`
- **Code → doc routing:** `unifai-dev-guide/guide-index.yaml` (maps `ui/client/src/**` to ui.md)
- **Source map:** `unifai-dev-guide/source-map.yaml → ui` (API modules, hooks, contexts, HTTP clients)

## Landmarks

| Landmark | Location |
|----------|----------|
| App entry | `App.tsx`, `main.tsx` |
| Route definitions | `pages/` |
| API client setup | `http/` |
| Build config | `vite.config.ts`, `tailwind.config.ts` |
| Nginx config | `ui/deployment/nginx.conf.template` |
| Proxy config (dev) | `ui/vite.config.ts` |
