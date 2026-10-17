# Tekos Tools

Three OKF Markdown bundles (ADR-0513, `zuno-okf-tool-v0.2.schema.json`),
each documenting usage of a tool some `../tasks/*.md` already declares in
`zuno.allowed_tools`: `search_confluence.md` (used by
`answer-technical-question` and `find-relevant-docs`, and
`answer-technical-question`'s `live_read_tool`), `web_search.md`
(`answer-technical-question`'s fallback - see
`../policies/web-search-scope.md` for the additional constraint on it),
and `list_drive_files.md` (`check-my-drive-docs`).

Documentary only - tool-call authorization stays each task's
`zuno.allowed_tools` intersected with `policies/tools/tool-policy.yaml`
and `platform/bindings/tools/tool-bindings.yaml`. These notes never grant
a tool call on their own.
