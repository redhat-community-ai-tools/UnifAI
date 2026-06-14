---
description: Hexagonal architecture guardrails for Python — layer placement, import direction, and critical safety patterns. For detailed mechanics and investigation techniques, load the architecture skill.
globs:
  - "**/*.py"
---

# Hexagonal Architecture — Python Guardrails

Always-on guardrails for everyday coding. Detailed reference (investigation techniques, per-layer error contract, SRP thresholds, test hygiene) lives in `.cursor/skills/architecture/hex-mechanics.md`.

## 1. Layer Placement Decision Tree

| Question | Yes → | No → |
|----------|-------|------|
| Does it call `subprocess`, `open()`, `shutil.which()`, `socket`, `requests`, or any filesystem/network/OS operation? | **Adapter** | ↓ |
| Does it orchestrate multiple ports/domain objects to fulfill a use case? | **Application Service** | ↓ |
| Does it define pure data, business rules, or computations with zero I/O? | **Domain** | ↓ |
| Is it an abstract interface (ABC) defining a contract? | **Port** | Reconsider design |

If a domain class does I/O, split it: pure domain class + adapter/loader.

## 2. Import Direction (Dependency Inversion)

```
domain/       → may import: stdlib, other domain modules
                must NOT import: ports/, adapters/, services/, frameworks

ports/        → may import: stdlib, domain/
                must NOT import: adapters/, services/, frameworks

services/     → may import: stdlib, domain/, ports/
                must NOT import: adapters/ (concrete classes)

adapters/     → may import: stdlib, domain/, ports/, frameworks, external libs
                must NOT import: services/ (except composition root)
```

Composition root (`cli.py`, app factory, `main()`) is the ONLY place where concrete adapters are instantiated and injected.

## 3. Port-per-Adapter

Every adapter must implement exactly one Port (ABC). A service importing a concrete adapter is a DIP violation.

## 4. Critical Safety Patterns

- `subprocess.run/call/Popen` → **list form only**. `shell=True` is a red flag.
- User-derived values in commands → `shlex.quote()`.
- Every `open()` inside `with` or `contextlib.ExitStack`.
- Enums for status values and type discriminators — not string literals.
