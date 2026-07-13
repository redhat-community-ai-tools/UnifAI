---
description: Universal engineering standards — SOLID, hexagonal architecture, Pydantic, enums, types, imports, naming, error handling, and Python safety patterns. Non-negotiable for all code.
globs:
  - "**/*.py"
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

Split an application service when:
- **8+ public methods** clustering into 3+ independent groups
- Method cluster A never calls methods in cluster B
- Generic name ("Orchestrator", "Manager", "Handler")

After decomposition: each focused service owns one cluster. A thin facade may remain for backward compatibility but must contain zero business logic.

---

## 2. Hexagonal Architecture

### Layer Placement Decision Tree

| Question | Yes | No |
|----------|-----|-----|
| Does it call `subprocess`, `open()`, `shutil.which()`, `socket`, `requests`, or any filesystem/network/OS operation? | **Adapter** | next |
| Does it orchestrate multiple ports/domain objects to fulfill a use case? | **Application Service** | next |
| Does it define pure data, business rules, or computations with zero I/O? | **Domain** | next |
| Is it an abstract interface (ABC) defining a contract? | **Port** | Reconsider design |

If a domain class does I/O, split it: pure domain class + adapter/loader.

### Import Direction (Dependency Inversion)

```text
domain/       may import: stdlib, other domain modules
              must NOT import: ports/, adapters/, services/, frameworks

ports/        may import: stdlib, domain/
              must NOT import: adapters/, services/, frameworks

services/     may import: stdlib, domain/, ports/
              must NOT import: adapters/ (concrete classes)

adapters/     may import: stdlib, domain/, ports/, frameworks, external libs
              must NOT import: services/ (except composition root)
```

Composition root (`cli.py`, app factory, `main()`) is the ONLY place where concrete adapters are instantiated and injected.

If a service contains `from project.adapters.xyz import ConcreteClass`, that is a DIP violation.

### Import Matrix (rings)

| Ring | Can Import | Cannot Import |
|------|-----------|---------------|
| Domain (`lib/mas/`) | Own domain code only | Adapters, Bootstrap |
| Adapters (`adapters/`) | Domain (to implement ports) | Bootstrap, other tech dirs |
| Bootstrap (`bootstrap/`) | Domain + Adapters | — (top level) |

Import direction is STRICTLY inward. No exceptions.

### Port-per-Adapter Rule

Every adapter class must implement exactly one Port (ABC).
- Adapter without a corresponding Port = missing abstraction
- Service directly instantiating or importing an adapter = DIP violation

### Domain-Specific Overrides

Each service's skill files contain an **"Established Patterns"** section that documents
pre-approved deviations. When a component's skill explicitly lists a pattern as established
practice, the domain skill takes precedence for that component. Reviewers MUST check the
relevant domain's Established Patterns table before flagging a violation.

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

| Rule | Example |
|------|---------|
| Every fixed value set = Enum | `SessionStatus`, `ResourceCategory` |
| Use `str, Enum` for JSON serialization | `class Status(str, Enum): ...` |
| Compare against enum, never string | `status == SessionStatus.RUNNING` not `status == "running"` |
| New values = explicit enum addition | Update all consumers |

Violations:
- `if status == "healthy"` should be `if status is ServiceStatus.HEALTHY`
- `type: str` field used for discrimination should be an Enum field

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
- NO inline imports (single exception: lazy imports in the composition root — `bootstrap/` — for conditional adapter wiring)
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

| Rule | Detail |
|------|--------|
| Specific domain exceptions | `SessionNotFoundError`, not generic `Exception` |
| Never catch bare `Exception` in business logic | Only in outermost adapter layer |
| Adapter wraps tech errors | `pymongo.errors.X` → domain exception |
| Always include context | `raise Error(f"Cannot upload {n} files, max is {max}")` |

### Per-Layer Error Contract

| Layer | May raise | May catch | Must NOT do |
|-------|-----------|-----------|-------------|
| **Domain** | `ValueError`, `KeyError`, custom domain exceptions | Nothing (let errors propagate) | `SystemExit`, `print()`, I/O |
| **Services** | `RuntimeError`, domain exceptions | Domain exceptions (to add context) | `SystemExit`, `print()` to stderr |
| **Adapters (CLI)** | `SystemExit` (at entry point only) | `RuntimeError`, `KeyError`, `FileNotFoundError` | Swallowing exceptions silently |
| **Adapters (API)** | HTTP status codes via framework | Service/domain exceptions | `SystemExit` |

A single error boundary at the CLI entry point (`main()`) is preferred over scattered `try/except`.

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

---

## 11. Python Safety Patterns

### Shell commands

- `subprocess.run/call/Popen` must use **list form**, never a single string
- User-derived values → `shlex.quote()` each argument
- Parsing command strings → `shlex.split()`, never `str.split()`
- `shell=True` → flag as **MAJOR** unless explicitly justified

### File safety

- Sensitive files (secrets, tokens, `.env`) → create with `os.open(path, flags, 0o600)`
- `# noqa` comments → investigate root cause, don't suppress

### Pattern matching

- Substring matching (`if name in content`) for service/process identification → use `re.search(rf"\b{re.escape(name)}\b", content)`

### Resource management

- Every `open()` must be inside `with` or `contextlib.ExitStack`
- Large files → stream or chunk, never `.read_text()` into memory
