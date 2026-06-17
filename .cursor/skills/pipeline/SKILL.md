---
name: pipeline
description: >-
  Multi-phase development pipeline orchestrating design, review, implementation,
  code review, QA, and debugging. Entry point for all /pipeline commands.
  Phases are loaded on demand from phases/ subdirectory.
---

# Pipeline Skill

Root skill for the multi-agent development pipeline. The pipeline orchestrator
(`.cursor/commands/pipeline.md`) drives the workflow; this skill provides
discovery metadata and navigation.

## Phase Files

Each phase has a dedicated instruction file loaded on demand by the orchestrator:

| Phase | File | Role |
|-------|------|------|
| 1 — Design | `phases/designer.md` | Software architect producing technical designs |
| 2 — Design Review | `phases/design-reviewer.md` | Skeptical reviewer challenging designs |
| 9 — Arch Review | `phases/arch-reviewer.md` | Architecture-focused review (standalone mode) |
| 3 — Implementation | `phases/coder.md` | Senior engineer writing production code |
| 4 — Code Review | `phases/code-reviewer.md` | Code reviewer + architecture gatekeeper |
| 5 — QA | `phases/qa.md` | QA automation engineer writing pytest tests |
| 6 — Debug | `phases/debugger.md` | Structured debugging methodology |

## Companion Skills

- **Architecture standards**: `.cursor/rules/engineering-standards.md` (universal coding rules)
- **Hex mechanics**: `.cursor/skills/architecture/references/investigation-techniques.md` (detailed hex enforcement, investigation techniques)
- **Codebase navigation**: `.cursor/skills/codebase/SKILL.md`
- **MAS domain knowledge**: `.cursor/skills/codebase/domains/multi-agent/SKILL.md`

## Feedback Loop

The orchestrator enforces revision loops between phases:
- Design Review → Designer (max 2 iterations)
- Code Review → Coder (max 2 iterations)
- QA → Coder + QA (max 2 iterations)

After exhausting revision limits, the pipeline stops and offers `/pipeline debug`.
