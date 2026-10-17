---
okf_version: v0.2
type: tool
title: Confluence page search
zuno:
  capability: search_confluence
  used_by_tasks:
    - answer-technical-question
    - find-relevant-docs
  live_read: true
  usage_notes: >-
    Searches internal Confluence spaces for content relevant to the
    current question or topic. In answer-technical-question it is the
    live_read_tool (ADR-0342/WP-33): the conditional live-read branch
    calls it when the indexed knowledge.tech corpus alone does not ground
    an answer, so results stay current between RAG ingestion runs. In
    find-relevant-docs it is the primary/only tool - a lookup task that
    returns matching pages without composing a narrative answer.
  known_limitations:
    - "C2 classification (policies/tools/tool-policy.yaml): results must
      not reach external/SaaS models (external_model_policy.allow_context:
      false), regardless of the task's own C1 preferred_classification
      ceiling."
---

# Confluence page search

Legacy pre-ADR-0116 name for the `confluence` MCP server's page-search
capability (`policies/tools/tool-policy.yaml`). Documentary only - actual
authorization stays `allowed_tools` (per task) intersected with
`policies/tools/tool-policy.yaml` and
`platform/bindings/tools/tool-bindings.yaml`.
