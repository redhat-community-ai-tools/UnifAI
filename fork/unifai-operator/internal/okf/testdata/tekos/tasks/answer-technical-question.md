---
okf_version: v0.2
type: task
title: Answer a technical question
zuno:
  allowed_tools:
    - search_confluence
    - web_search
    - git.repository.read
    - git.repository.list
    # ADR-0516: a deliberate, narrow carve-out - Tekos gets diagram
    # generation (Mermaid-to-SVG, never leaves the cluster) for technical
    # questions that call for an architecture/sequence/relationship
    # diagram, but still never declares image.generation.create
    # (photorealistic/illustrative SDXL content stays Arkos/Comage's
    # job - see evaluations/tekos/security_checks.py's
    # tekos_chat_never_returns_photorealistic_images and gate_checks.py's
    # tekos_declares_no_dat_or_image_generation_capability, both updated
    # alongside this to assert exactly that boundary).
    - diagram.generation.create
    # ADR-0355/WP-074: AAP audits. Tekos is the only agent declaring
    # aap.cluster.audit - the one capability in this repository that RUNS
    # cluster automation rather than reading state. Its case is the
    # infrastructure-question one this task exists for ("is the cluster
    # healthy right now?"), which no other agent's task set covers; Arkos
    # gets the read-only half only. tool-policy.yaml gives both entries the
    # same allowed_groups on purpose, so THIS declaration is the factor
    # actually holding the read/action line - do not copy it to another
    # agent without re-reading ADR-0355's Security considerations.
    - aap.platform.audit
    - aap.cluster.audit
  live_read_tool: search_confluence
  allowed_knowledge:
    - knowledge.tech
    - knowledge.project
  # ADR-0515: editable starters. Shown in the chat empty state, and in the
  # composer's slash menu (agent-frontend web/src/chat/TaskPromptMenu.tsx).
  # UX only - never parsed or enforced server-side, and picking one does NOT
  # select this task: the chat route always runs primary_task (ADR-0342).
  prompt_examples:
    - "How do I configure Keycloak as the OIDC identity provider for an OpenShift cluster?"
    - "What is the difference between a Route and an Ingress on OpenShift?"
    - "How does Argo CD decide that an Application is out of sync?"
---

# Answer a technical question

Answer a free-form technical question using the Tekos RAG corpus (official
OpenShift/Kubernetes/Keycloak/Ansible/Argo CD/Helm/Go documentation) plus
internal Confluence content first, falling back to a constrained web
search when the internal corpus has no grounded answer. Every answer
includes concise source citations.

This is the task the Agent Runtime's chat endpoint (`POST
/v1/agents/tekos/chat`) executes for every turn in v0 - see
`components/agent-runtime/app/registry.py` (ADR-0039) for how its
`allowed_tools` above and `prompts/answer-technical-question.md`'s system
prompt are resolved into the running LangGraph workflow.

ADR-0121: `git.repository.read`/`git.repository.list` add read-only
GitHub/GitLab repository access (`components/mcp-servers/git-forge`,
ADR-0120) alongside Confluence/web search - **public repositories only,
on either provider**. Tekos never declares the private-scoped
`git.repository.private.*` capabilities (GitLab private access, reserved
for Arkos) or any write/create capability.
