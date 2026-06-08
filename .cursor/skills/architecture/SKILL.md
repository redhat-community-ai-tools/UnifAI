---
name: architecture-standards
description: >-
  Universal engineering standards enforced across all services in this repository.
  SOLID principles, hexagonal architecture, Pydantic models, enums, type hints,
  import conventions, error handling, and naming. These rules are non-negotiable
  and apply to every file regardless of which service it belongs to.
---

# Architecture Standards

## How to Use

Load `standards.md` whenever writing or reviewing code in this repository.
These rules apply universally — they are not service-specific.

## Structure

```
architecture/
└── standards.md     Universal coding rules (SOLID, hex, Pydantic, enums, types, imports)
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
