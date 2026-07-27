---
name: ui-knowledge
description: >-
  Domain knowledge for the UnifAI frontend. React/TypeScript SPA with feature-oriented
  layout. Use when working on files under ui/client/src/.
paths: ui/client/src/**
---

# UI Knowledge System

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
| `useBuiltinEditLockSession` | Repository Mgmt | Owns heartbeat/release lifecycle for one held admin edit-lock |
| `useBuiltinEditLockPoll` | Repository Mgmt | Polls lock-holder status for built-in resources (admin panel) |

## Nginx Path Routing (production)

| Path | Target | Notes |
|------|--------|-------|
| `/api1/*` | RAG (port 13457) | Standard proxy |
| `/api2/*` | MAS (port 8002) | Streaming: 600s timeout, `proxy_buffering off` |
| `/api3/*` | Identity | 307 redirect to `IDENTITY_HOST` |
| `/api4/*` | Platform (port 8005) | Standard proxy |

## Dev-Guide Facts

For full endpoint catalog (72 endpoints), component details, and hook documentation:
- **Service doc:** `.cursor/unifai-dev-guide/docs/services/ui.md`
- **Code → doc routing:** `.cursor/unifai-dev-guide/guide-index.yaml` (maps `ui/client/src/**` to ui.md)
- **Source map:** `.cursor/unifai-dev-guide/source-map.yaml → ui` (API modules, hooks, contexts, HTTP clients)

## Landmarks

| Landmark | Location |
|----------|----------|
| App entry | `App.tsx`, `main.tsx` |
| Route definitions | `pages/` |
| API client setup | `http/` |
| Build config | `vite.config.ts`, `tailwind.config.ts` |
| Nginx config | `ui/deployment/nginx.conf.template` |
| Proxy config (dev) | `ui/vite.config.ts` |

## Domain Rules

Frontend-specific conventions. Note: UI does NOT follow hexagonal architecture —
it uses feature-oriented layout instead.

---

### 1. Feature-Oriented Layout

Each feature is self-contained in its directory with its own components,
hooks, and types. Shared code lives in top-level `components/`, `hooks/`,
`contexts/`, and `lib/`.

---

### 2. API Layer Separation

All backend communication goes through the `api/` layer. Components never
make direct HTTP calls. Hooks wrap API functions and use TanStack React Query v5
for server state management.

---

### 3. Type Safety

All API responses, component props, and state shapes have explicit TypeScript
interfaces. No `any` types in production code. Shared types in `types/`.

---

### 4. Workspace Identity Pattern

`useWorkspaceIdentity()` is the single source of truth for `userId`, `identityType`
(user vs team), and `displayName`. It feeds API params for every identity-scoped call.
Backed by `AuthContext` (session) + `ViewContext` (team switching).

---

### 5. Component Conventions

- Functional components only (no class components)
- Props destructured in function signature
- Custom hooks for logic extraction (heavy components → dedicated hooks)
- Composition over inheritance
- shadcn/ui primitives from `components/ui/` — do not reinvent

---

### 6. Streaming Pattern

NDJSON streaming via native `fetch` + `ReadableStream` (not axios).
`useSessionStream` hook handles submit → subscribe → reconnect.
`StreamingDataContext` holds `Map<nodeId, NodeEntry>` for live graph overlays.

---

### 7. Graph Builder (JointJS)

Two modes: Creation (`useGraphCreationLogic` + `useGraphCreationCanvas`) and
Display (`useGraphDisplay`). YAML-backed with dagre auto-layout.
Team mode adds edit locks — one editor per blueprint at a time.

---

### 8. Admin Edit Locks (Repository Management)

The Repository Management panel (built-in resource admin) mirrors the team edit-lock
pattern from #7, but for admins editing shared built-ins instead of team members
editing a shared blueprint: `useBuiltinEditLockSession` (heartbeat/release for a held
lock) + `useBuiltinEditLockPoll` (poll other admins' lock status) against the
`builtin.edit_lock.*` endpoints. One admin edits a given built-in at a time; acquiring
is cooperative client-side, but the mutating endpoints reject with 409 if another
admin holds the lock, so it is a real server-enforced guard.

---

### 9. Built-in vs. Custom Resources (Ownership Model)

Every `ElementInstance` (`types/workspace.ts`) carries `ownership?: 'builtin' | 'custom'`,
`visibility?: 'draft' | 'public'`, and `userConfigured?: boolean`, mirroring the
backend's `ResourceOwnership`/`ResourceVisibility` (see
`domains/multi-agent/references/resources.md`). Two pages consume this:

- **Agent Repository** (`pages/AgentRepository.tsx`) — end-user view, filterable
  All / Built-in / Personal; configuring a built-in (`BuiltinConfigureModal`) writes
  a per-identity overlay (`userConfigured=true`), never the shared base.
- **Configuration → Repository Management** (`features/configuration/RepositoryManagement.tsx`
  + `repository-management/`) — admin-only: create/edit/delete built-ins, toggle
  "available to all" (`draft`↔`public`, with `CascadeConfirmDialog` for dependent
  resources), promote a custom resource to built-in.

`useWorkspaceData` is the shared hook for both — routing built-in-specific calls
(`configureBuiltin`, `saveBuiltinElement`, `toggleBuiltinStatus`, schema/user-config
fetch) through `api/resources.ts`'s `builtins.*` methods alongside the plain CRUD
methods it already had.

---

### 10. OAuth Popup Message Validation

Any UI flow that opens an OAuth "sign in" popup and relays the result back via
`window.opener.postMessage()` MUST validate the incoming message with
`isTrustedCredentialsCallback()` (`lib/oauthPopupSecurity.ts`) — checking both
`event.source === popup` and `event.origin` against the callback origin recovered
from the authorization URL's `redirect_uri`. Do not add a bare `message` event
listener for a new OAuth flow without this check (a same-object-different-origin
popup navigation could otherwise spoof the callback).

---

### Established Patterns — UI Frontend

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| Feature-oriented layout instead of hexagonal architecture | Entire `ui/client/src/` | React SPA — hex doesn't apply; features, hooks, contexts replace ports/adapters |
| Large context files (700+ LOC) | `AgenticAIContext` (~760 LOC) | Client-side cache + validation orchestration; splitting fragments tightly coupled state |
| Large hooks (1400+ LOC) | `useGraphCreationLogic` (~1470 LOC) | Graph builder state machine; complexity is inherent, not decomposable without prop-drilling |
| `AgenticAIContext` calls API/axios directly (bypasses hook layer) | `contexts/AgenticAIContext.tsx` | Resource maps and validation caches require batch fetching at context init; hook indirection adds no value |
| `AuthContext` uses `http/authClient` directly | `contexts/AuthContext.tsx` | Auth is the boundary — session management can't go through a domain API layer |
| Some components import `@/api/*` without hook wrappers | `TeamSettingsModal`, `SharedPanel`, etc. | Simple one-off API calls where a hook would be trivial; TanStack React Query adoption is partial |
| Nested provider tree (7–8 contexts deep) | `App.tsx` | Standard React cross-cutting state; each context has a clear single responsibility |
| Streaming via native `fetch` (not Axios) | `useSessionStream` | NDJSON streaming requires `ReadableStream` API; Axios doesn't support streaming reads |
| Card fields driven generically by server-side schema hints (`hints.card`, `hints.secret`, `hints.hidden`, `hints.conditional`) instead of per-element-type switch statements | `lib/cardFields.ts#getCardFields()`, consumed by `BuiltInElementCard`, `ElementGrid` | Mirrors the backend `field_hints.py` contract (see `domains/multi-agent/references/elements.md`) — adding a new element type never requires touching card-rendering code, only its config schema |
