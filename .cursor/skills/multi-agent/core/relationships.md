---
name: core-relationships
scope: Deep implementation details for core contracts flowing into other components
parent: _index.md
when_to_load: Changing identity propagation, execution context lifecycle, or ElementDeps injection chain
---

# Core → All (Identity Propagation)

## Full Path

```
Flask decorator → resolves Identity from token/headers
  → service method(identity=...) → embedded in SessionRecord
  → embedded in ExecutionContext → available to elements via holder
```

## Repository Scoping

ALL repository queries MUST include identity scope:
```python
def find_by_id(self, session_id: str, identity: Identity) -> Optional[SessionRecord]:
    query = {"_id": session_id, **identity_q(identity)}
```

---

# Core → Session (ExecutionContext Lifecycle)

```
create_session(): ExecutionContext(identity, session_id, run_id, blueprint_id)
  → stored in SessionRecord.run_context
staging: updated with engine_handle (if submit)
lifecycle.begin(): holder.context = record.run_context  # NOW available
lifecycle.complete(): mark_finished()
```

Accessing `holder.context` before `lifecycle.begin()` raises RuntimeError (fail-fast).

---

# Core → Elements (ElementDeps Chain)

## Adding New Infrastructure to Elements

Full chain from config to element:

```
config/app_config.py: new_feature_key = ""
  → container.py: if cfg.new_feature_key: factory = lambda: NewThing(cfg.key)
  → WorkflowSessionFactory.__init__(new_factory=factory)
  → build_session(): ElementDeps(new_factory=factory)
  → SessionElementBuilder: passes deps as kwargs
  → ElementFactory.create(**kwargs): extracts new_factory from kwargs
  → Element uses factory at runtime
```

## Port → Adapter Complete Mapping

| Domain Port | Adapter |
|-------------|---------|
| `SessionRepository` | `MongoSessionRepository` |
| `BlueprintRepository` | `MongoBlueprintRepository` |
| `ResourceRepository` | `MongoResourceRepository` |
| `BackgroundSessionEngine` | `TemporalSessionEngine` |
| `IFileUploadService` | `GeminiFileUploadAdapter` |
| `BaseGraphBuilder` | `LangGraphBuilder` / `TemporalGraphBuilder` |
| `BaseGraphExecutor` | `LangGraphExecutor` / `TemporalGraphExecutor` |
| `ChannelFactory` | `RedisChannelFactory` / `LocalChannelFactory` |
| `CollaborationStore` | `RedisCollaborationStore` |
| `IdentityProvider` | `IdentityPodProvider` / `DevProvider` / `NoOpProvider` |
| `AuthStrategy` | `OAuth2Strategy` / `ApiKeyStrategy` |
| `CredentialStore` | `MongoCredentialStore` |
| `FlowStateStore` | `RedisFlowStateStore` |
