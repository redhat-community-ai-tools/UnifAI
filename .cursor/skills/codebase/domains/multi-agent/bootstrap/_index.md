---
name: mas-bootstrap
scope: Composition root (container.py) and application configuration (app_config.py)
parent: ../_index.md
when_to_load: Adding new services, wiring adapters, adding config parameters, or debugging startup
---

# Bootstrap & Configuration

Composition root — the outermost ring that knows about everything. Wires ports to adapters.

## Dependency Graph

```
  ENTRY POINTS (run/dev.py, wsgi.py, temporal/__main__.py)
       │
       ▼
  ┌─BOOTSTRAP─────────────────────────────┐
  │ AppContainer(cfg)                       │
  │   imports: mas.* (domain) + outbound.* │
  │   exposes: services as attributes       │
  └────────────────────────────────────────┘
       │ passes container to
       ▼
  INBOUND (Flask app.container = container)
```

## Structure

```
bootstrap/container.py     AppContainer — single composition root
config/app_config.py       AppConfig — all config with defaults
```

## Wiring Order in Container

1. **Discovery** — ElementRegistry, ActionsService auto-discover
2. **Repositories** — Mongo repos (depend on config only)
3. **Registries** — ResourcesRegistry, BlueprintResolver
4. **Services** — Domain services with deps injected
5. **Auth layer** — Strategies, detector, AuthService
6. **Session layer** — Factory, manager, lifecycle, projector, runner
7. **Identity** — Provider selection based on config mode
8. **Optional features** — Guarded by config value presence

## Config Conventions

| Pattern | Example |
|---------|---------|
| Empty string = disabled | `gemini_api_key: str = ""` |
| Sensible defaults | `engine_name: str = "temporal"` |
| No secrets in defaults | Keys default empty, set via env |
| Grouped by concern | Comments separate sections |

## How to Add a New Service

1. Import service class + adapter(s) at top of `container.py`
2. Instantiate adapter with `cfg.*` values
3. Instantiate service with dependencies injected
4. Expose as `self.<service_name>` attribute
5. Create Flask endpoint blueprint if needed

## How to Add a New Config Parameter

1. Add typed field to `config/app_config.py` with default
2. Use in `container.py`: `cfg.<field_name>`
3. If optional feature: guard with `if cfg.<field>:`

## Conditional Feature Pattern

```python
if cfg.feature_key:
    from outbound.<tech>.<module> import Adapter
    adapter = Adapter(cfg.feature_key)
else:
    adapter = None
# Service handles None gracefully
```

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| Add new service | Flask endpoint registration | Expose API |
| Add new adapter | `config/app_config.py` | Config source |
| Change service constructor | Container wiring | Injection args |
| Add conditional feature | Config + container guard | Feature flag |

## Rules

- Container is NEVER imported by domain or adapter code (only entry points)
- Constructor injection only — no service locator
- Lazy imports for optional heavy adapters only
- No global state

## Established Patterns — Bootstrap

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `SingletonMeta` on `AppContainer` | `bootstrap/container.py` | Process-wide singleton needed for multi-entry-point service (Flask + Temporal + CLI); first-construction-wins |
| Conditional `if cfg.<feature>:` with lazy imports for optional adapters | `container.py` | Feature flags for optional heavy adapters (Gemini, Temporal); prevents import of unused deps |

## Boundaries

**Owns:** object graph assembly, adapter instantiation, config reading.
**Does NOT own:** business logic, domain rules, adapter implementation details.
