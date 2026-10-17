---
okf_version: v0.2
type: rag
title: Technical documentation retrieval
zuno:
  domain: knowledge.tech
  used_by_tasks:
    - answer-technical-question
    - find-relevant-docs
  freshness_expectation: semantic-read
  rationale: >-
    Tekos's core value is grounded technical Q&A: answer-technical-question
    retrieves from knowledge.tech first (falling back to web_search only
    when the internal corpus has no grounded answer, ADR-0205), and
    find-relevant-docs is a pure knowledge.tech lookup/browse task. No
    per-domain top_k override is needed today - both tasks use the
    agent-wide zuno.rag.top_k (5, see agent.okf.md).
---

# Technical documentation retrieval

Tekos's primary knowledge domain (ADR-0202): official product
documentation plus internal Confluence content. No retrieval tuning
diverges from the agent-wide default here, so this note is purely a
cross-reference back to the two tasks that declare it.

Documentary only - this file does not change what retrieve_node actually
requests (`agent.okf.md`'s `zuno.rag.top_k`) or what is authorized
(`tasks/*.md`'s `zuno.allowed_knowledge` intersected with
`policies/knowledge/knowledge-policy.yaml`). See `knowledge/tech/domain.yaml`
for the domain's own taxonomy and freshness objective.

**Known gap, partly closed 2026-09-03.** `knowledge/tech/domain.yaml`'s
`technology_vocabulary` lists only `satellite`, `openshift`,
`openshift-ai`, `keycloak`, while Tekos's own `agent.okf.md`/README
describe its corpus as spanning OpenShift, Kubernetes, Keycloak, Ansible,
Argo CD, Helm and Go documentation. That mismatch was not theoretical: the
corpus held **no** Argo CD, Helm or Go content at all, and
`evaluations/tekos/stress_test.py`'s `qa-argocd`/`qa-helm`/`qa-go` probes
were nonetheless scoring 7/7 - passing on unrelated OpenShift chunks,
because `components/rag-service/app/search.py`'s `_vector_query` has no
relevance threshold and the check only asserts `len(citations) > 0`. It
surfaced only when the vector arm degraded to full-text-only and full-text
correctly found nothing.

Argo CD and Helm are now ingested (`gitops/charts/rag-ingestion/
values.yaml`: Red Hat OpenShift GitOps 1.17/1.16, and Helm via OpenShift's
*Building applications* guide 4.22/4.21). **Go is still absent and is a
real gap**: docs.redhat.com carries no Go documentation the `fetch-redhat`
adapter could take, and the Go Toolset material that exists documents Red
Hat's packaging of the compiler, not the language semantics `qa-go` asks
about. Covering it needs a generic-web source adapter for go.dev -
`SOURCE_ADAPTERS` has only `fetch-redhat`/`fetch-confluence`/
`fetch-salesforce`/`load-sxa-dump` - which is its own work package.
Updating `knowledge/tech/domain.yaml`'s vocabulary to match what is now
actually ingested still belongs to whoever next edits it.
