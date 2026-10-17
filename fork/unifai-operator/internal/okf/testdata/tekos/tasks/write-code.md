---
okf_version: v0.2
type: task
title: Write code
zuno:
  allowed_tools: []
  allowed_knowledge: []
  # ADR-0515: editable starters. Shown in the chat empty state, and in the
  # composer's slash menu (agent-frontend web/src/chat/TaskPromptMenu.tsx).
  # UX only - never parsed or enforced server-side, and picking one does NOT
  # select this task: the chat route always runs primary_task (ADR-0342).
  prompt_examples:
    - "Write an Ansible task that waits for a Deployment to finish rolling out."
    - "Generate a Kubernetes NetworkPolicy allowing ingress only from the istio-system namespace."
    - "Write a Go function that verifies an RS256 JWT against a JWKS endpoint."
---

# Write code

Generate code, configuration or a script (Terraform, Ansible, Kubernetes
manifests, Helm, shell, Python, Go, ...) directly in the chat reply -
distinct from `answer-technical-question`'s documentation-grounded Q&A,
which a request like this has nothing to do with.

Declared for the OKF catalog (ADR-0417), same "declared, not live-routed
by itself" status Tekos's other non-primary tasks (`find-relevant-docs`,
`check-my-drive-docs`) already have (`primary_task` stays
`answer-technical-question` - `GraphFactory` never builds a graph for
`write-code` directly). It is referenced only as the `task_name` label
`app/graph/nodes.py::_make_code_node` passes to
`ModelRouter.invoke_with_fallback` for one heuristic-triggered branch of
Tekos's single live `retrieve_reason_respond` graph
(`_make_route_after_retrieval`), the same task-name-as-routing-label
mechanism ADR-0417 established for Arkos's `code_node`.
`allowed_tools`/`allowed_knowledge` are deliberately empty: this branch
makes no MCP tool call of its own, though it does still run after
`retrieve_node` and may use whatever RAG context that call already
fetched.

`policies/model-routing/model-routing-policy.yaml`'s `(tekos, write-code)`
entry is non-strict, `prefer: [mistral-codestral, local-gpt-oss, local]` -
Tekos is C1-seeded, so Codestral (`eligible_for: [C1, C2]`) is reachable
at its natural classification with no override, and the existing generic
fallback-on-any-exception in the AI Gateway already drops to local if
Codestral errors for any reason (including the account running low on
credits) - "use local also for coding" falls out of this ordering alone,
no live credit detection needed.
