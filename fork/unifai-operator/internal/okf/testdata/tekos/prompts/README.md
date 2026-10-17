# Tekos Prompts

`answer-technical-question.md` (ADR-0038 OKF Markdown bundle format) is the
`reason` node's system prompt, loaded at startup by
`components/agent-runtime/app/registry.py` (ADR-0039) rather than
hardcoded in `app/graph/nodes.py`.
