---
name: ui-rules
scope: Frontend-specific patterns and conventions
parent: _index.md
when_to_load: Writing or reviewing code in ui/client/src/
---

# UI Rules

Frontend-specific conventions. Note: UI does NOT follow hexagonal architecture —
it uses feature-oriented layout instead.

---

## 1. Feature-Oriented Layout

Each feature is self-contained in its directory with its own components,
hooks, and types. Shared code lives in top-level `components/`, `hooks/`,
`contexts/`, and `lib/`.

---

## 2. API Layer Separation

All backend communication goes through the `api/` layer. Components never
make direct HTTP calls. Hooks wrap API functions and use TanStack React Query v5
for server state management.

---

## 3. Type Safety

All API responses, component props, and state shapes have explicit TypeScript
interfaces. No `any` types in production code. Shared types in `types/`.

---

## 4. Workspace Identity Pattern

`useWorkspaceIdentity()` is the single source of truth for `userId`, `identityType`
(user vs team), and `displayName`. It feeds API params for every identity-scoped call.
Backed by `AuthContext` (session) + `ViewContext` (team switching).

---

## 5. Component Conventions

- Functional components only (no class components)
- Props destructured in function signature
- Custom hooks for logic extraction (heavy components → dedicated hooks)
- Composition over inheritance
- shadcn/ui primitives from `components/ui/` — do not reinvent

---

## 6. Streaming Pattern

NDJSON streaming via native `fetch` + `ReadableStream` (not axios).
`useSessionStream` hook handles submit → subscribe → reconnect.
`StreamingDataContext` holds `Map<nodeId, NodeEntry>` for live graph overlays.

---

## 7. Graph Builder (JointJS)

Two modes: Creation (`useGraphCreationLogic` + `useGraphCreationCanvas`) and
Display (`useGraphDisplay`). YAML-backed with dagre auto-layout.
Team mode adds edit locks — one editor per blueprint at a time.

---

## Established Patterns — UI Frontend

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
