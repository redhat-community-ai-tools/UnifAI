---
name: engineering-standards
scope: Universal coding standards enforced across all services
when_to_load: Writing or reviewing any code in this repository
---

# Engineering Standards

Non-negotiable rules for ALL code in this repository. Violations must be fixed before merge.

---

## 1. SOLID Principles

| Principle | Rule | Violation Sign |
|-----------|------|----------------|
| **SRP** | One class = one reason to change | Class described with "and" |
| **OCP** | Extend via new classes, not modifying existing | Adding `if/elif` chains for new types |
| **LSP** | Subtypes substitutable for base | Adapter breaks port contract |
| **ISP** | Small focused interfaces | Implementors forced to stub methods |
| **DIP** | Depend on abstractions, not concretions | Importing adapter from domain |

---

## 2. Hexagonal Architecture

> For detailed mechanics (layer placement decision tree, full import matrix, per-layer error contract,
> investigation techniques, Python safety patterns) see `hex-mechanics.md` in this skill.

| Ring | Can Import | Cannot Import |
|------|-----------|---------------|
| Domain (`lib/mas/`) | Own domain code only | Adapters, Bootstrap |
| Adapters (`adapters/`) | Domain (to implement ports) | Bootstrap, other tech dirs |
| Bootstrap (`bootstrap/`) | Domain + Adapters | — (top level) |

Import direction is STRICTLY inward. No exceptions.

---

## 3. Pydantic Models — Always

| Use For | Rule |
|---------|------|
| All structured data crossing boundaries | Pydantic BaseModel |
| Immutable value objects | `model_config = {"frozen": True}` |
| Mutable defaults | `Field(default_factory=list)` |
| Constraints | `Field(ge=0)`, `@field_validator` |
| Never | Bare `dict` for structured data, `Any` for typed fields |

---

## 4. Enums — No Magic Strings

> For specific violation patterns and enforcement examples, see `hex-mechanics.md` §6.

| Rule | Example |
|------|---------|
| Every fixed value set = Enum | `SessionStatus`, `ResourceCategory` |
| Use `str, Enum` for JSON serialization | `class Status(str, Enum): ...` |
| Compare against enum, never string | `status == SessionStatus.RUNNING` not `status == "running"` |
| New values = explicit enum addition | Update all consumers |

---

## 5. Type Hints — Mandatory

| Rule | Applies To |
|------|-----------|
| Full annotations on all signatures | Functions, methods, class attributes |
| Return type always declared | Use `-> None` for void |
| `Optional[X]` explicit | Never leave nullable implicit |
| Use `TYPE_CHECKING` for type-only imports | Avoids circular imports |

---

## 6. Imports — Top of File Only

| Position | Contents |
|----------|----------|
| First | Standard library (`import logging`, `from typing import ...`) |
| Second | Third-party (`from pydantic import ...`, `from flask import ...`) |
| Third | Local domain (`from mas.core.identity import Identity`) |
| Fourth | Local adapters (only in adapter/bootstrap code) |

**Rules:**
- NO inline imports (single exception: lazy imports in `container.py` for optional heavy adapters)
- NO wildcard imports (`from x import *`)
- NO circular imports (refactor if needed)

---

## 7. No Hardcoded Values

| Instead of... | Use... |
|---------------|--------|
| Magic numbers in logic | Named constants (`MAX_FILES = 10`) |
| Connection strings in code | Config parameters |
| Feature behavior in code | Config flags |
| Raw strings for statuses | Enums |

---

## 8. Error Handling

> For the per-layer error contract (what each layer may raise/catch), see `hex-mechanics.md` §4.

| Rule | Detail |
|------|--------|
| Specific domain exceptions | `SessionNotFoundError`, not generic `Exception` |
| Never catch bare `Exception` in business logic | Only in outermost adapter layer |
| Adapter wraps tech errors | `pymongo.errors.X` → domain exception |
| Always include context | `raise Error(f"Cannot upload {n} files, max is {max}")` |

---

## 9. Naming

| Thing | Convention | Example |
|-------|-----------|---------|
| Classes | PascalCase | `SessionService` |
| Functions/methods | snake_case | `upload_batch` |
| Constants | UPPER_SNAKE | `MAX_FILES_PER_UPLOAD` |
| Private | Leading `_` | `_validate_files` |
| Files/dirs | snake_case | `session_repository.py` |
| Enums | PascalCase + UPPER values | `SessionStatus.RUNNING` |

---

## 10. Documentation

| When | What |
|------|------|
| Every public class | One-line docstring minimum |
| Non-obvious behavior | Explain WHY, not WHAT |
| Constraints/invariants | Document in docstring or comment |
| Never | Narrate obvious code, explain what code does line-by-line |
