---
okf_version: v0.2
type: agent
title: Tekos
description: >-
  Technical consultant assistant. Answers technical questions grounded in
  official product documentation and internal Confluence content, with
  concise citations, and helps consultants locate relevant reference
  material across the RAG corpus and their own Drive.
provenance:
  maintainer: Zuno Demo architecture team
  repository: zuno-demo
verification:
  status: unverified
freshness:
  last_reviewed: "2026-08-05"
sources:
  - "technical-docs (RAG corpus: OpenShift/Kubernetes/Keycloak/Ansible/Argo CD/Helm/Go documentation)"
  - confluence
zuno:
  name: tekos
  status: active
  graph_shape: retrieve_reason_respond
  primary_task: answer-technical-question
  tasks:
    - answer-technical-question
    - find-relevant-docs
    - check-my-drive-docs
    - write-code
  rag:
    top_k: 5
  model:
    preferred_classification: C1
    notes: >-
      Public vendor/product documentation and general technical Q&A are C1
      (SaaS model use allowed). Answers that incorporate Confluence content
      must respect Confluence's C2 classification (policies/data-classification)
      for the portions of context drawn from it, even though the task's
      ceiling here is C1. The concrete model catalog lives in
      platform/ai-gateway/provider-routing.yaml (not a model name here by
      design); this agent's answer-technical-question preference
      ([local-gpt-oss, local]) lives in
      policies/model-routing/model-routing-policy.yaml — the resolved
      effective chain is generated below in "Model routing".
  access:
    # ADR-0040: agent entitlement group, orthogonal to the `consultant`
    # business role that governs tool/data permissions inside Tekos
    # (policies/tools/tool-policy.yaml).
    groups:
      - agent_tekos
  ui:
    displayName: Tekos
    tileDescription: Technical Q&A with citations, for consultants.
    color: "#0066CC"
    icon: code
---

# Tekos

Technical consultant assistant. Tekos is the only agent with `status:
active` for v0 (MEMORY.md section 9, docs/agents/tekos.md): it is the
first vertical slice and validates frontend, BFF, Keycloak, runtime, AI
gateway, RAG, MCP Confluence, model routing, streaming and citations end
to end.

Conforms to `platform/okf/schema/zuno-okf-v0.2.schema.json` (ADR-0005,
ADR-0006, ADR-0038). Task detail lives in `tasks/*.md`, linked by name from
`zuno.tasks` above; the system prompt for the primary task lives in
`prompts/answer-technical-question.md`.

`zuno.graph_shape: retrieve_reason_respond` (ADR-0342) names the LangGraph
workflow module (`components/agent-runtime/app/graph/shapes/`) Agent
Runtime's `GraphFactory` resolves for Tekos's chat turns - retrieve, an
optional live tool call, reason, respond. Naming it declaratively here (no
prior behavior change) is what lets a later agent reuse this exact shape,
or Arkos declare a materially different one, without any Agent Runtime
code change.

Tekos has no agent-level `zuno.allowed_knowledge` field (ADR-0203): like its
tool ceiling, its knowledge-domain ceiling is derived as the union of every
task's own `zuno.allowed_knowledge`
(`components/agent-runtime/app/registry.py:AgentDefinition.declared_knowledge()`,
mirroring `declared_tools()`) rather than declared separately here - today
that union is `[knowledge.tech]`, from `tasks/answer-technical-question.md`
and `tasks/find-relevant-docs.md`.

<!-- BEGIN GENERATED AUTHORIZATION MATRIX (ADR-0503) - do not edit; regenerate with: python3 platform/okf/generate_authorization_matrix.py -->

## Authorization matrix

Generated per ADR-0503 from this bundle's frontmatter, `policies/tools/tool-policy.yaml`, `policies/knowledge/knowledge-policy.yaml`, `platform/ai-gateway/provider-routing.yaml` and `policies/model-routing/model-routing-policy.yaml` — the enforced intersection (ADR-0011/ADR-0203) restated for review, never read at runtime. Entitlement (ADR-0040): `agent_tekos`; model classification ceiling (ADR-0021): `C1`; status: `active`.

| Task (FOR WHAT) | Resource (WHAT) | Kind | Capability / server | Min class | Business roles (WHO) | Ext-model context | Quota | Policy source |
|---|---|---|---|---|---|---|---|---|
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `search_confluence` (live-read) | tool | `confluence.page.search` @ confluence | C2 | consultant, board, cdp, lightspeed_readonly | blocked | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `search_confluence` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `web_search` | tool | `web.page.search` @ web-search | C1 | sales, consultant, adv, finance, board | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `web_search` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `git.repository.read` | tool | `git.repository.read` @ git-forge | C2 | consultant, board, cdp | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `git.repository.read` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `git.repository.list` | tool | `git.repository.list` @ git-forge | C2 | consultant, board, cdp | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `git.repository.list` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `diagram.generation.create` | tool | `diagram.generation.create` @ diagram-gen | C1 | consultant, adv, sales, board, cdp | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `generate_diagram` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `aap.platform.audit` | tool | `aap.platform.audit` @ aap | C2 | consultant, board, cdp | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `aap.platform.audit` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `aap.cluster.audit` | tool | `aap.cluster.audit` @ aap | C2 | consultant, board, cdp | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `aap.cluster.audit` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `knowledge.tech` | knowledge | — | — | consultant, board, cdp | — | `standard` (user 60 req/5m) | `knowledge/knowledge-policy.yaml` `knowledge.tech` |
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `knowledge.project` | knowledge | — | — | consultant, board, sales, adv, finance, cdp | — | `standard` (user 60 req/5m) | `knowledge/knowledge-policy.yaml` `knowledge.project` |
| `find-relevant-docs` | `search_confluence` | tool | `confluence.page.search` @ confluence | C2 | consultant, board, cdp, lightspeed_readonly | blocked | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `search_confluence` |
| `find-relevant-docs` | `knowledge.tech` | knowledge | — | — | consultant, board, cdp | — | `standard` (user 60 req/5m) | `knowledge/knowledge-policy.yaml` `knowledge.tech` |
| `check-my-drive-docs` | `list_drive_files` | tool | `drive.document.search` @ google-workspace | C1 | consultant, board, cdp, sales, adv, finance | allowed | `standard` (user 60 req/5m) | `tools/tool-policy.yaml` `list_drive_files` |

### Model routing

Effective per-task model chain (ADR-0021/ADR-0303/ADR-0412), resolved from `platform/ai-gateway/provider-routing.yaml`'s classification eligibility reordered by this `(agent, task)`'s `policies/model-routing/model-routing-policy.yaml` preference — the first entry is the reference model, the rest are fallback alternatives, in try order. The reference model is annotated with the model id it actually serves and that model's architectural role (`default`, `quality`, `reasoning`, `specialized`, `reasoning-external`, `code`, `general-external`); `provider-routing.yaml`'s `role` key is the authority for both, and every model reachable through the fallback chain is named in the **Available models** rollup below the table.

| Task | Classification ceiling | Reference model | Fallback chain | Adapter | Policy source |
|---|---|---|---|---|---|
| `answer-technical-question` (primary; prompt: `prompts/answer-technical-question.md`) | `C1` | `ovhcloud-gpt-oss-120b` → `gpt-oss-120b` (reasoning-external) | `local-gpt-oss-maas`, `local-gpt-oss`, `local-qwen35-maas`, `local-qwen35`, `local-wesh-maas`, `local-wesh`, `local-maas`, `local`, `openai`, `gemini`, `anthropic`, `mistral`, `mistral-codestral` | — | `policies/model-routing/model-routing-policy.yaml` |
| `find-relevant-docs` | `C1` | `local-qwen35-maas` → `qwen3.5-9b` (default) | `local-qwen35`, `local-wesh-maas`, `local-wesh`, `local-maas`, `local`, `local-gpt-oss-maas`, `local-gpt-oss`, `ovhcloud-gpt-oss-120b`, `openai`, `gemini`, `anthropic`, `mistral`, `mistral-codestral` | — | `policies/model-routing/model-routing-policy.yaml` |
| `check-my-drive-docs` | `C1` | `local-qwen35-maas` → `qwen3.5-9b` (default) | `local-qwen35`, `local-wesh-maas`, `local-wesh`, `local-maas`, `local`, `local-gpt-oss-maas`, `local-gpt-oss`, `ovhcloud-gpt-oss-120b`, `openai`, `gemini`, `anthropic`, `mistral`, `mistral-codestral` | — | `policies/model-routing/model-routing-policy.yaml` |
| `write-code` | `C1` | `mistral-codestral` → `codestral-latest` (code) | `local-wesh-maas`, `local-wesh`, `local-gpt-oss-maas`, `local-gpt-oss`, `local-maas`, `local`, `local-qwen35-maas`, `local-qwen35`, `openai`, `gemini`, `anthropic`, `mistral`, `ovhcloud-gpt-oss-120b` | — | `policies/model-routing/model-routing-policy.yaml` |

**Available models** (ADR-0419, generated): the union of every model reachable by any task or prompt slot above, at any classification, each with the model id it serves and that model's role - `local-maas` → `qwen3.6-27b-instruct` (quality), `local` → `qwen3.6-27b-instruct` (quality), `local-gpt-oss-maas` → `gpt-oss-20b` (reasoning), `local-gpt-oss` → `gpt-oss-20b` (reasoning), `local-wesh-maas` → `qwen3.5-9b-wesh` (specialized), `local-wesh` → `qwen3.5-9b-wesh` (specialized), `local-qwen35-maas` → `qwen3.5-9b` (default), `local-qwen35` → `qwen3.5-9b` (default), `openai` → `gpt-4o-mini` (general-external), `gemini` → `gemini-1.5-pro` (general-external), `anthropic` → `claude-3-5-sonnet-latest` (general-external), `mistral` → `mistral-large-latest` (general-external), `mistral-codestral` → `codestral-latest` (code), `ovhcloud-gpt-oss-120b` → `gpt-oss-120b` (reasoning-external).

<!-- END GENERATED AUTHORIZATION MATRIX -->
