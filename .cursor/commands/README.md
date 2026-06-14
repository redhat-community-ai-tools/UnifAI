# Cursor Commands

Custom Cursor IDE commands for the UnifAI project. Invoke with `/` in the Cursor chat.

## Primary Command

### `/pipeline` — Multi-Phase Development Pipeline

The unified development workflow. Replaces all legacy standalone commands with an integrated multi-agent pipeline featuring design, review, implementation, code review, QA, and debugging phases with automatic revision loops.

**Modes:**

| Mode | Usage | Phases |
|------|-------|--------|
| `full` (default) | `/pipeline <task or Jira ticket>` | Design → Review → Implement → Code Review → QA |
| `design-only` | `/pipeline design-only <task>` | Design only |
| `design-and-review` | `/pipeline design-and-review <task>` | Design → Design Review |
| `implement` | `/pipeline implement <design-file>` | Implement → Code Review → QA |
| `review-only` | `/pipeline review-only <design-file>` | Design Review only |
| `code-review-only` | `/pipeline code-review-only [files]` | Code Review only |
| `qa-only` | `/pipeline qa-only [files]` | QA only |
| `debug` | `/pipeline debug <error>` | Structured debugging |
| `arch-review` | `/pipeline arch-review [files]` | Architecture review (CI mode) |

**Options:**
- `--adr` — Write design to ADR file at `docs/designs/<slug>-adr.md`

**Examples:**
```
/pipeline design-only --adr Add caching layer for vector search
/pipeline full GENIE-1234
/pipeline code-review-only rag/core/pipeline/
/pipeline implement docs/designs/caching-adr.md
/pipeline debug "PipelineExecutor fails with empty source list"
```

---

## Utility Commands

### `/push` — Design Document Uploader
Uploads design files to Jira tickets.

```
/push <jira-ticket> <file-name>
```

### `/review` — Quick Branch Review
Lightweight code review for current branch changes.

```
/review [basic|deep] [files/folders]
```

---

## Deprecated Commands

These commands are superseded by `/pipeline` modes. They remain functional but will be removed in a future cleanup pass.

| Legacy Command | Replaced By |
|---------------|-------------|
| `/Code.Review` | `/pipeline code-review-only` |
| `/Hexagonal.Gatekeeper` | `/pipeline code-review-only` or `arch-review` |
| `/Hexagonal.Refactor` | `/pipeline implement <design>` |
| `/PyTest.GateKeeper` | `/pipeline qa-only` |
| `/design` | `/pipeline design-only --adr` |

---

## Skills System

Pipeline commands load phase-specific instruction files from `.cursor/skills/pipeline/phases/`:

| Phase | Skill File |
|-------|-----------|
| Design | `phases/designer.md` |
| Design Review | `phases/design-reviewer.md` |
| Arch Review | `phases/arch-reviewer.md` |
| Implementation | `phases/coder.md` |
| Code Review | `phases/code-reviewer.md` |
| QA | `phases/qa.md` |
| Debug | `phases/debugger.md` |

Domain knowledge is loaded from `.cursor/skills/codebase/` (routing table) and service-specific domain skills under `codebase/domains/` and `multi-agent/`.

Architecture standards are enforced via:
- `.cursor/rules/hexagonal-python.md` — hexagonal architecture mechanics
- `.cursor/skills/architecture/standards.md` — universal coding rules

---

**Last Updated:** June 2026
**Project:** UnifAI
