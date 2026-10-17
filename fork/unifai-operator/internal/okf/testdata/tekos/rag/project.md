---
okf_version: v0.2
type: rag
title: Project memory retrieval
zuno:
  domain: knowledge.project
  used_by_tasks:
    - answer-technical-question
  freshness_expectation: semantic-read
  rationale: >-
    answer-technical-question also retrieves knowledge.project (ADR-0209)
    so a consultant's grounded answer can draw on durable, cross-session
    memory scoped to their current engagement (project_id), not just the
    static documentation corpus. This domain has no ingestion schedule to
    tune against - knowledge/project/domain.yaml's freshness objective is
    on-write (memory becomes retrievable the moment Agent Runtime's
    memory-extraction step runs at session end), so no staleness/top_k
    override applies here.
---

# Project memory retrieval

Cross-session, cross-agent project memory (ADR-0209), scoped by
`project_id` and written directly by Agent Runtime's extraction step -
never ingested by `components/rag-ingestion`. See
`knowledge/project/domain.yaml`.

Documentary only, same posture as `rag/tech.md`: this file narrows or
explains what `answer-technical-question.md`'s `zuno.allowed_knowledge`
and `policies/knowledge/knowledge-policy.yaml` already authorize - it
grants nothing on its own.
