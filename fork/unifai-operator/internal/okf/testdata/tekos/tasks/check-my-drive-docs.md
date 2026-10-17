---
okf_version: v0.2
type: task
title: Check my Drive documents
zuno:
  allowed_tools:
    - list_drive_files
  # ADR-0515: editable starters. Shown in the chat empty state, and in the
  # composer's slash menu (agent-frontend web/src/chat/TaskPromptMenu.tsx).
  # UX only - never parsed or enforced server-side, and picking one does NOT
  # select this task: the chat route always runs primary_task (ADR-0342).
  prompt_examples:
    - "List my Drive documents about the satellite run architecture."
    - "Which of my documents mention the Keycloak migration?"
---

# Check my Drive documents

List the authenticated consultant's own Google Drive documents that are
relevant to a given project or topic, using delegated end-user OAuth2 so
only files the user can already see are listed (ADR-0014).

Declared for the OKF catalog (ADR-0038); no distinct Agent Runtime route
exists for it yet in v0 - the single `POST /v1/agents/tekos/chat` endpoint
only executes `answer-technical-question`. Wiring a dedicated route for
this task is v1 scope.
