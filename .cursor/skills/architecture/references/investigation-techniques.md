# Deep Investigation Techniques & Test Hygiene

Loaded on demand by pipeline review phases. Universal standards are always active
via `.cursor/rules/engineering-standards.md`.

---

## Test Hygiene

- Tests reading `os.environ` must use `monkeypatch.setenv`/`delenv` — never rely on the developer's shell
- After refactoring: test file names must mirror the module they test
- After moving modules: update ALL test imports — run `pytest --collect-only` to verify
- Test helpers constructing service objects must match the current constructor signature

---

## Investigation Techniques

Agents must not accept code at face value. Apply these before issuing any verdict.

### Import Chain Tracing

For every new or modified module, trace its FULL import chain:
1. Read the file's imports
2. For each project import, read THAT file's imports
3. Classify each by layer (domain / port / service / adapter / framework)
4. Flag any forbidden boundary crossing

A service importing a utility that imports an adapter is still a violation — the dependency is transitive.

### Caller Analysis

Before approving any change to a function's signature, return type, or error behavior:
1. Search the entire codebase for all callers
2. Verify each caller handles the new behavior correctly
3. Pay attention to: changed return types, new exceptions, removed `SystemExit`

### Constructor Dependency Audit

For every service or adapter class:
1. Read the `__init__` method
2. List every dependency parameter
3. Verify each dependency is a Port (ABC), not a concrete class
4. Trace WHERE the concrete implementation is injected — must be composition root only

### "What Does It Actually Do?" Test

For any module whose placement is questioned:
1. Read the entire file
2. List every stdlib/external call (`subprocess`, `open`, `socket`, `shutil`, `os.*`, `requests`, etc.)
3. If it makes ANY I/O call → adapter, regardless of where it currently lives
4. If it only manipulates data and calls ports → service

Do not trust the filename or directory — trust what the code does.

### Error Propagation Path Tracing

For every function that raises an exception or calls `sys.exit`:
1. Trace the call stack upward to the entry point
2. At each level: does the caller catch this? What if it doesn't?
3. If `SystemExit` is raised below the CLI layer, check whether any caller above would be silently aborted

### Composition Root Inspection

Read the composition root and verify:
1. Every service receives dependencies via constructor injection
2. No service instantiates its own adapters
3. The error boundary catches the right exception types
4. Concrete adapter classes appear ONLY here and in tests

### Cross-Reference Path Validation

When code constructs file paths (`Path(__file__).parent / "something"`):
1. Count `.parent` calls and verify they land in the right directory
2. Check from the file's ACTUAL location
3. Verify the target file exists

### Test Impact Analysis

After any refactoring:
1. Search test files for imports of the changed module path
2. Search for constructor calls to the changed class
3. Search for string references to old names (mock patches like `@patch("project.services.old_module.func")`)
4. Verify test file names still mirror the module they test
