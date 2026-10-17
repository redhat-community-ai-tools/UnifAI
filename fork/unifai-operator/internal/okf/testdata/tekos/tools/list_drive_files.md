---
okf_version: v0.2
type: tool
title: List Drive files
zuno:
  capability: list_drive_files
  used_by_tasks:
    - check-my-drive-docs
  usage_notes: >-
    Lists the authenticated consultant's own Google Drive documents
    relevant to a given project or topic, using delegated end-user OAuth2
    (ADR-0014) so only files the caller can already see are ever listed.
  known_limitations:
    - "Declared for the OKF catalog only in v0 - no distinct Agent Runtime
      route exists for check-my-drive-docs yet; the single POST
      /v1/agents/tekos/chat endpoint only executes
      answer-technical-question. Wiring a dedicated route is v1 scope."
---

# List Drive files

Documentary only - actual authorization stays `allowed_tools` (per task)
intersected with `policies/tools/tool-policy.yaml` and
`platform/bindings/tools/tool-bindings.yaml`.
