# Tekos Rag

Two OKF Markdown bundles (ADR-0513, `zuno-okf-rag-v0.2.schema.json`), each
documenting retrieval tuning for a knowledge domain some `../tasks/*.md`
already declares in `zuno.allowed_knowledge`: `tech.md` (`knowledge.tech`,
used by `answer-technical-question` and `find-relevant-docs`) and
`project.md` (`knowledge.project`, used by `answer-technical-question`).

Documentary only - retrieval actually runs on `../agent.okf.md`'s
`zuno.rag.top_k` and each task's `zuno.allowed_knowledge`, authorized
against `policies/knowledge/knowledge-policy.yaml`. These notes narrow or
explain that contract; they never grant retrieval access on their own.
