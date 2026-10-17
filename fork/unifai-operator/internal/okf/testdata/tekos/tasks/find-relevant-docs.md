---
okf_version: v0.2
type: task
title: Find relevant documentation
zuno:
  allowed_tools:
    - search_confluence
  allowed_knowledge:
    - knowledge.tech
  # ADR-0515: editable starters. Shown in the chat empty state, and in the
  # composer's slash menu (agent-frontend web/src/chat/TaskPromptMenu.tsx).
  # UX only - never parsed or enforced server-side, and picking one does NOT
  # select this task: the chat route always runs primary_task (ADR-0342).
  prompt_examples:
    - "Find the Confluence pages describing the satellite build architecture."
    - "Which documentation covers OpenShift AI model serving?"
    - "List the reference material we have on Keycloak realm configuration."
---

# Find relevant documentation

Given a topic or keyword, return the most relevant internal Confluence
pages and RAG-indexed documentation sections without composing a full
narrative answer - a lookup/browse task for consultants scanning available
material before a customer call.

Declared for the OKF catalog (ADR-0038); no distinct Agent Runtime route
exists for it yet in v0 - the single `POST /v1/agents/tekos/chat` endpoint
only executes `answer-technical-question`. Wiring a dedicated route for
this task is v1 scope.
