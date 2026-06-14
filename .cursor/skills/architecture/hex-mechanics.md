---
name: hex-mechanics
scope: Detailed hexagonal architecture mechanics, investigation techniques, and Python safety patterns
when_to_load: During pipeline review phases, refactoring, or when detailed hex rules are needed
---

# Hexagonal Architecture — Detailed Mechanics

Authoritative reference for hexagonal architecture enforcement in this Python codebase.
Loaded on demand by pipeline phases and the architecture skill.

---

## 1. Layer Placement Decision Tree

| Question | Yes → | No → |
|----------|-------|------|
| Does it call `subprocess`, `open()`, `shutil.which()`, `socket`, `requests`, or any filesystem/network/OS operation? | **Adapter** | ↓ |
| Does it orchestrate multiple ports/domain objects to fulfill a use case? | **Application Service** | ↓ |
| Does it define pure data, business rules, or computations with zero I/O? | **Domain** | ↓ |
| Is it an abstract interface (ABC) defining a contract? | **Port** | Reconsider design |

**Domain+loader split**: If a domain class does I/O, split it — pure domain class (holds parsed data, typed lookups) + adapter/loader (reads from external source, constructs domain object).

---

## 2. Import Rules (Dependency Inversion)

Enforce by reading actual `import`/`from` statements:

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

**Composition root** (`cli.py`, app factory, `main()`) is the ONLY place where concrete adapters are instantiated, injected into services, and the global error boundary lives.

If a service contains `from project.adapters.xyz import ConcreteClass`, that is a DIP violation.

**Domain-specific overrides:** Each service's skill files (`_index.md`, `rules.md`)
contain an **"Established Patterns"** section that documents pre-approved deviations
from the general hex rules above. When a component's skill explicitly lists a pattern
as established practice, the domain skill takes precedence over §1–§2 for that component.
Reviewers MUST check the relevant domain's Established Patterns table before flagging
a violation — if the pattern is listed there, it is pre-approved and must not be flagged.

All domains have Established Patterns tables:
MAS (elements, engine-graph, adapters, bootstrap, core), RAG, Identity, Backend, UI,
Global Utils, Celery, and Temporal Worker.

---

## 3. Port-per-Adapter Rule

Every adapter class must implement exactly one Port (ABC).
- Adapter without a corresponding Port → missing abstraction
- Service directly instantiating or importing an adapter → DIP violation

---

## 4. Error Handling Layer Contract

| Layer | May raise | May catch | Must NOT do |
|-------|-----------|-----------|-------------|
| **Domain** | `ValueError`, `KeyError`, custom domain exceptions | Nothing (let errors propagate) | `SystemExit`, `print()`, I/O |
| **Services** | `RuntimeError`, domain exceptions | Domain exceptions (to add context) | `SystemExit`, `print()` to stderr |
| **Adapters (CLI)** | `SystemExit` (at entry point only) | `RuntimeError`, `KeyError`, `FileNotFoundError` | Swallowing exceptions silently |
| **Adapters (API)** | HTTP status codes via framework | Service/domain exceptions | `SystemExit` |

A single error boundary at the CLI entry point (`main()`) is preferred over scattered `try/except`.
Functions below the CLI layer must return error data or raise typed exceptions — never `sys.exit()`.

---

## 5. SRP Decomposition Threshold

Split an application service when:
- **8+ public methods** clustering into 3+ independent groups
- Method cluster A never calls methods in cluster B
- Generic name ("Orchestrator", "Manager", "Handler")

After decomposition: each focused service owns one cluster. A thin facade may remain for backward compatibility but must contain zero business logic.

---

## 6. Enum Enforcement

Status values, strategy identifiers, and type discriminators must be **Enums**, not string literals.

Violations:
- `if status == "healthy"` → should be `if status is ServiceStatus.HEALTHY`
- `KEYCLOAK_KEYS = {"keycloak_base_url", ...}` → should be `frozenset` constant
- `type: str` field used for discrimination → should be an Enum field

---

## 7. Python Safety Patterns

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

---

## 8. Test Hygiene

- Tests reading `os.environ` must use `monkeypatch.setenv`/`delenv` — never rely on the developer's shell
- After refactoring: test file names must mirror the module they test
- After moving modules: update ALL test imports — run `pytest --collect-only` to verify
- Test helpers constructing service objects must match the current constructor signature

---

## 9. Deep Investigation Techniques

Agents must not accept code at face value. Apply these before issuing any verdict.

### 9.1 Import Chain Tracing
For every new or modified module, trace its FULL import chain:
1. Read the file's imports
2. For each project import, read THAT file's imports
3. Classify each by layer (domain / port / service / adapter / framework)
4. Flag any forbidden boundary crossing (see §2)

A service importing a utility that imports an adapter is still a violation — the dependency is transitive.

### 9.2 Caller Analysis
Before approving any change to a function's signature, return type, or error behavior:
1. Search the entire codebase for all callers
2. Verify each caller handles the new behavior correctly
3. Pay attention to: changed return types, new exceptions, removed `SystemExit`

### 9.3 Constructor Dependency Audit
For every service or adapter class:
1. Read the `__init__` method
2. List every dependency parameter
3. Verify each dependency is a Port (ABC), not a concrete class
4. Trace WHERE the concrete implementation is injected — must be composition root only

### 9.4 "What Does It Actually Do?" Test
For any module whose placement is questioned:
1. Read the entire file
2. List every stdlib/external call (`subprocess`, `open`, `socket`, `shutil`, `os.*`, `requests`, etc.)
3. If it makes ANY I/O call → adapter, regardless of where it currently lives
4. If it only manipulates data and calls ports → service

Do not trust the filename or directory — trust what the code does.

### 9.5 Error Propagation Path Tracing
For every function that raises an exception or calls `sys.exit`:
1. Trace the call stack upward to the entry point
2. At each level: does the caller catch this? What if it doesn't?
3. If `SystemExit` is raised below the CLI layer, check whether any caller above would be silently aborted

### 9.6 Composition Root Inspection
Read the composition root and verify:
1. Every service receives dependencies via constructor injection
2. No service instantiates its own adapters
3. The error boundary catches the right exception types
4. Concrete adapter classes appear ONLY here and in tests

### 9.7 Cross-Reference Path Validation
When code constructs file paths (`Path(__file__).parent / "something"`):
1. Count `.parent` calls and verify they land in the right directory
2. Check from the file's ACTUAL location
3. Verify the target file exists

### 9.8 Test Impact Analysis
After any refactoring:
1. Search test files for imports of the changed module path
2. Search for constructor calls to the changed class
3. Search for string references to old names (mock patches like `@patch("project.services.old_module.func")`)
4. Verify test file names still mirror the module they test
