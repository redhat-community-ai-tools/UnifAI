---
okf_version: v0.2
type: tool
title: Constrained web search
zuno:
  capability: web_search
  used_by_tasks:
    - answer-technical-question
  usage_notes: >-
    Fallback path only: answer-technical-question tries the indexed
    knowledge.tech/knowledge.project corpus and search_confluence's live
    read first (ADR-0205, prefer indexed knowledge for reads); web_search
    is invoked only when neither grounds an answer. Every answer still
    carries concise source citations regardless of which path produced it.
  known_limitations:
    - "Widest-reach, least-controlled tool this agent declares: no
      classification/ACL metadata comes back with results the way
      RAG chunks or Confluence pages carry it. See
      agents/tekos/policies/web-search-scope.md for the additional scope
      constraint this agent applies to it."
---

# Constrained web search

Documentary only - actual authorization stays `allowed_tools` (per task)
intersected with `policies/tools/tool-policy.yaml` and
`platform/bindings/tools/tool-bindings.yaml`.
