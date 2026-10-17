# Tekos Agent

- **Purpose:** Technical consultant assistant
- **Primary integrations:** Official technical RAG, Confluence, web search
- **Initial tasks:** Technical Q&A with concise citations; first MVP vertical slice

## Stage (ADR-0502)

**Stage 2 — promoted** (grandfathered on criterion b: Tekos deliberately
stays on plain manifests as the ADR-0350/ADR-0308 coexistence proof — it
is the one agent whose deployment interface is not an `AIAgent` CR).

- `zuno.status: active`; the only agent with a live Agent Runtime route
  (`POST /v1/agents/tekos/chat`, `retrieve_reason_respond` graph shape).
- Deployed by `gitops/charts/tekos/` (raw Deployment/Service/Route set)
  via `gitops/apps/api/application-d1.yaml`.
- Evaluations: `evaluations/tekos/` is the canonical shared
  implementation every other agent's wrappers delegate to (ADR-0342);
  Tekos cleared the ADR-0027/0028 gates as the v0 vertical slice
  (ADR-0031).
- Stage-2 criterion c is structural debt shared by every agent:
  `deployment/` and `tests/` gain their real ADR-0503/ADR-0504 content
  with WP-45/WP-46; `policies/`, `rag/` and `tools/` gain theirs with
  WP-56/ADR-0513.

**Next step:** none for promotion (already Stage 2); migrating off plain
manifests remains a deliberate non-goal while the coexistence proof
stands.

## Declarative structure (ADR-0038: OKF v0.2 Markdown bundles)

```text
tekos/
├── README.md
├── agent.okf.md         Agent index bundle (YAML frontmatter + Markdown body)
├── tasks/
│   ├── answer-technical-question.md   (primary task, the live chat route)
│   ├── find-relevant-docs.md
│   └── check-my-drive-docs.md
├── prompts/
│   └── answer-technical-question.md   System prompt, loaded by app/registry.py
├── policies/            1 narrowing-only addendum (ADR-0513, WP-56)
├── rag/                 2 per-domain retrieval notes (ADR-0513, WP-56)
├── tools/               3 per-tool usage notes (ADR-0513, WP-56)
├── deployment/          Generated ADR-0503 snapshot + README (WP-45)
└── tests/               ADR-0504 structure (WP-46; suites fill at promotion)
```

The earlier `agent.okf.yaml` (a single Kubernetes-style YAML file) was
replaced by `agent.okf.md` plus linked per-task/per-prompt Markdown
documents under `tasks/`/`prompts/` per ADR-0038.

The runtime implementation is shared. This directory contains only
agent-specific declarative behavior, policy, knowledge references and
deployment configuration.
