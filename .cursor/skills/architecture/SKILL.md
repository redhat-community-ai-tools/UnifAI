---
name: architecture-standards
description: >-
  Universal engineering standards and hexagonal architecture mechanics for this repository.
  Standards cover SOLID, Pydantic, enums, type hints, imports, error handling, and naming.
  Hex-mechanics covers layer placement, import rules, investigation techniques, and Python safety.
  These rules are non-negotiable and apply to every file regardless of which service it belongs to.
---

# Architecture Standards

## How to Use

- Load `standards.md` whenever writing or reviewing code — universal coding rules.
- Load `hex-mechanics.md` during pipeline reviews, refactoring, or when detailed hexagonal enforcement is needed.

## Structure

```
architecture/
├── standards.md       Universal coding rules (SOLID, Pydantic, enums, types, imports, naming)
└── hex-mechanics.md   Detailed hex mechanics (layers, import matrix, error contract, investigation techniques, safety patterns)
```

## Quick Reference

| Rule | Summary |
|------|---------|
| SOLID | SRP, OCP, LSP, ISP, DIP — all enforced |
| Hexagonal | Domain → Adapters → Bootstrap. Import direction strictly inward. |
| Pydantic | All structured data uses Pydantic models. No bare dicts. |
| Enums | All fixed value sets use enums. No magic strings/numbers. |
| Type Hints | Every function signature fully annotated. No exceptions. |
| Imports | All at top of file. stdlib → third-party → local. No inline imports. |
| No Hardcoding | Named constants or config. Never raw literals in logic. |
| Errors | Specific domain exceptions. Never bare Exception catch. |
| Naming | PascalCase classes, snake_case functions/files, UPPER constants. |
