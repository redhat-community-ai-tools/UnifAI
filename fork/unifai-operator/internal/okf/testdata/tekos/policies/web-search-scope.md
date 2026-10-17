---
okf_version: v0.2
type: policy
title: Web search fallback scope
zuno:
  narrows_platform_policy: true
  constraint_type: data_handling_addendum
  applies_to:
    tasks:
      - answer-technical-question
    tools:
      - web_search
  rationale: >-
    web_search is answer-technical-question's fallback when the indexed
    knowledge.tech/knowledge.project corpus and search_confluence's live
    read (ADR-0205) do not ground an answer. Unlike those two paths, its
    results carry no classification/ACL metadata on the way back, and the
    query text itself leaves the platform boundary to an external search
    provider. This agent additionally restricts web_search queries to
    public technical topics only: no customer name, project_id, or other
    content derived from the knowledge.project domain may be included in a
    web_search query, even though the task's declared
    preferred_classification (C1)
    would otherwise permit the call. This is strictly narrower than what
    policies/tools/tool-policy.yaml already permits for web_search - it
    grants nothing web_search's existing policy entry doesn't already
    allow.
  enforcement:
    mechanism: none-yet
    notes: >-
      Followed by prompt convention today (see
      prompts/answer-technical-question.md), not code-enforced. A future
      MCP Gateway request-content filter on the web_search binding, or an
      Agent Runtime guard before the tool call, would close this gap -
      recorded here as a documented gap rather than a false claim of
      enforcement (ADR-0513).
---

# Web search fallback scope

Additional, agent-specific constraint on Tekos's `web_search` fallback.
Narrows only - see `zuno.narrows_platform_policy` above and
`policies/tools/tool-policy.yaml`'s own `web_search` entry for the
platform floor this constraint sits inside of.
