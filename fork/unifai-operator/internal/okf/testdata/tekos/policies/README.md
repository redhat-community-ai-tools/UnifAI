# Tekos Policies

One OKF Markdown bundle so far (ADR-0513, `zuno-okf-policy-v0.2.schema.json`):
`web-search-scope.md`, an agent-specific, narrowing-only constraint on the
`web_search` fallback in `answer-technical-question`.

Platform-wide policies (tool/knowledge authorization, quotas, data
classification) live at the repository root under `policies/` and are not
duplicated here - this directory is only for constraints Tekos adds on top
of that floor. Each file's `zuno.narrows_platform_policy: true` is a
schema-enforced acknowledgment that it can restrict, never grant or widen,
what `policies/*/` and Tekos's own tasks already allow.
