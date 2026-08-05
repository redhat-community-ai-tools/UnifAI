# Resources & Blueprints Component

Resources are the persisted, reusable building blocks (LLMs, tools, providers, retrievers,
nodes, conditions) that blueprints reference by `rid`. Blueprints are the graph
definitions that combine inline configs and resource refs into an executable spec.

## Architecture

```text
   BLUEPRINTS                          RESOURCES
   BlueprintService                    ResourcesService (facade)         BuiltinResourceService (peer facade)
      │ resolve(draft, caller) ──────►   │                                  │
      ▼                                   ├─ CRUD, validation, cards          ├─ descriptor CRUD, visibility gating
   BlueprintResolver                      ├─ get_descriptor/is_builtin/         admin promote/demote/toggle + cascade
      │ walks Refs via _ResolveSession    │  resolve_config/cleanup_on_delete   per-identity overlay get/save/resolve
      ▼                                   │  ──────► self._builtin (peer) ◄──┘  schema exposure
   resources_service.resolve(rid, caller)  └─ uses ResourceFieldEncryption   └─ uses ResourceFieldEncryption
                                                                                  builtin_resource_descriptor_repo
```

`ResourcesService` and `BuiltinResourceService` are **both** public facades,
constructed as peers in `bootstrap/container.py` and injected independently
into whatever needs them — `ResourcesService` composes `BuiltinResourceService`
internally only for the handful of generic-CRUD helper methods it needs
(`get_descriptor`, `is_builtin`, `is_visible_to`, `resolve_config`,
`validation_override_error`, `cleanup_on_delete`), never for the admin/overlay
surface. Flask's `builtins.py`, `ShareCloner`, and tests that need the admin
lifecycle inject/consume `BuiltinResourceService` directly — `ResourcesService`
carries zero pass-through methods and zero knowledge of the
`ResourceOwnership`/`ResourceVisibility` enums.

`CallerScope` (`mas/core/caller_scope.py`) is a single frozen dataclass —
`CallerScope(identity: Optional[Identity], is_admin: bool)` — bundling "who is
calling and what can they see". It replaces separately threading `identity`
and `is_admin` through every method signature down this whole chain: adding a
new caller attribute (e.g. a feature flag) only means adding a field to
`CallerScope`, not touching every intermediate method signature (Open/Closed).

`BlueprintResolver` and `ShareCloner` depend on narrow read-only Protocols —
`ResourceReader` (`get_visible`, `resolve_resource`), `ResourceClonePort`
(`get`, `save_resource`, `exists_by_name`, `delete`), and `BuiltinDescriptorReader`
(`get_descriptor`) — all in `mas/resources/ports.py` — rather than the full
`ResourcesService`/`BuiltinResourceService` (Dependency Inversion).
`ResourcesService`/`BuiltinResourceService` satisfy these structurally (no
inheritance needed, `typing.Protocol`); `bootstrap/container.py` injects the
one concrete instance of each into every consumer that needs it.

### Structure

```text
lib/mas/resources/
├── models.py                    Resource, ResourceQuery — zero built-in-related fields/knowledge
├── registry.py                  ResourcesRegistry — thin persistence wrapper (uniqueness, in-use checks)
├── service.py                   ResourcesService — the public facade for base CRUD (see below)
├── builtin_service.py           BuiltinResourceService — peer facade for descriptor lifecycle + admin/overlays
├── builtin_models.py            BuiltinResourceDescriptor, BuiltinUpdateRequest, BuiltinUserConfig, identity_to_key()
├── field_encryption.py          ResourceFieldEncryption — schema-hint scan + encrypt/decrypt (shared collaborator)
├── ports.py                     CredentialCleanupPort, ResourceReader, ResourceClonePort, BuiltinDescriptorReader (narrow Protocols)
├── errors.py                    Resource*Error, BuiltIn*Error, Builtin*Error
├── resolver.py                  DependencyResolver (nested_refs / cascade helpers used by registry)
└── repository/
    ├── base.py                  ResourceRepository (ABC) — no built-in-related methods
    ├── builtin_resource_descriptor_repository.py   BuiltinResourceDescriptorRepository (ABC) — descriptor CRUD + $lookup-joined reads
    └── builtin_user_config_repository.py   BuiltinUserConfigRepository (ABC)

lib/mas/blueprints/
├── resolver.py                  BlueprintResolver — walks Refs via _ResolveSession, resolves live resources
├── service.py                   BlueprintService — save/load/resolve/validate blueprints
└── models/blueprint.py          BlueprintDraft, BlueprintSpec, BlueprintResource

lib/mas/core/
└── caller_scope.py               CallerScope — frozen (identity, is_admin) value object
```

### Key Contracts

| Class | Role |
|-------|------|
| `CallerScope` | Frozen `(identity: Optional[Identity], is_admin: bool)` value object. Resolved once per request (`resolve_caller_scope()` in `adapters/inbound/flask/decorators.py`) and passed as a single `caller` parameter into `ResourcesService`/`BlueprintService`/`BlueprintResolver` instead of two separately-threaded parameters. |
| `ResourcesService` | Public facade for base resource CRUD/validation/cards. ALL external access to those concerns (Flask `resources.py`, `BlueprintResolver`, `ShareCloner`, tests) goes through this — never through `ResourcesRegistry` directly. Composes `BuiltinResourceService` (`self._builtin`, internal attribute) only for the small set of built-in-awareness helpers its own CRUD methods need; has no admin/overlay pass-through methods and never touches `ResourceOwnership`/`ResourceVisibility` directly. |
| `BuiltinResourceService` | Peer public facade — sole owner of `BuiltinResourceDescriptor`'s full lifecycle: descriptor CRUD, visibility gating (`is_builtin`, `is_visible_to`), admin create/promote/demote/toggle + cascade, per-identity overlay get/save/resolve, schema exposure. Flask `builtins.py` injects it directly (`container.builtin_resource_service`) rather than going through `ResourcesService`. Deliberately **not** on `CallerScope` — `get_builtin_schema(rid, is_admin=...)` keeps its own separate `is_admin` param since it's already the "built-in admin boundary" the rest of this refactor routes around. |
| `ResourceFieldEncryption` (`self._fields` on both services) | Single owner of schema-hint scanning (`scan_schema_hints`) and encrypt/decrypt, shared by base CRUD and built-in overlays so behavior never drifts between the two paths. `bootstrap/container.py` constructs one instance and injects it into both services. |
| `ResourcesRegistry` | Thin persistence wrapper: uniqueness guard, in-use checks. Not the public API. Shared by both `ResourcesService` and `BuiltinResourceService` (same `resources` collection, no built-in-related fields on the documents it stores). |
| `BuiltinResourceDescriptorRepository` (`resources/repository/builtin_resource_descriptor_repository.py`) | Storage port for `BuiltinResourceDescriptor` — CRUD by `rid`, plus `$lookup`-joined reads (`find_all_builtins`, `find_visible_for_identity`) that combine descriptor metadata with the base `resources` collection, since `Resource` itself carries nothing to filter/sort on for those queries. |
| `ResourceReader` / `ResourceClonePort` / `BuiltinDescriptorReader` (`resources/ports.py`) | Narrow read-only Protocols. `BlueprintResolver` depends on `ResourceReader` (`get_visible`, `resolve_resource`); `ShareCloner` depends on `ResourceClonePort` (`get`, `save_resource`, `exists_by_name`, `delete`) and `BuiltinDescriptorReader` (`get_descriptor`) — separate Protocols (Interface Segregation) since each consumer needs a different narrow slice. `ResourcesService`/`BuiltinResourceService` satisfy these structurally. |
| `BlueprintResolver` | Walks a `BlueprintDraft`'s Refs via a private `_ResolveSession` (bundles `caller` + per-call mutable state), resolves external refs via `ResourceReader.get_visible()`/`resolve_resource()` (built-in overlay aware when `caller.identity` is set), builds the executable `BlueprintSpec`. |

## Built-in Resources System

Built-ins let an admin curate a shared library of pre-configured elements
(LLMs, MCP servers, tools, agent nodes) that end users can use without
configuring credentials/URLs themselves, while still letting each user
override the small set of fields the admin marked as user-configurable
(e.g. their own MCP bearer token).

### Ownership & Visibility

```python
class ResourceOwnership(str, Enum):   # lib/mas/core/enums.py — query-filter value only, never a Resource field
    BUILTIN = "builtin"
    CUSTOM = "custom"

class ResourceVisibility(str, Enum):  # lib/mas/core/enums.py
    DRAFT = "draft"     # admin-only visibility
    PUBLIC = "public"   # visible to all end users


class BuiltinResourceDescriptor(BaseModel):   # lib/mas/resources/builtin_models.py
    """Stored in its own `builtin_resource_descriptors` collection, joined to
    `resources` by `rid`. Existence of a descriptor for a given `rid` *is*
    the "this resource is a built-in" signal — there is no `ownership` field
    to keep in sync with that existence."""
    rid: str
    visibility: ResourceVisibility = ResourceVisibility.DRAFT
    parent_builtin_id: Optional[str] = None
    created: datetime
    updated: datetime
```

`Resource` (`resources/models.py`) carries **no** built-in-related fields at
all — `ownership`, `visibility`, and `parent_builtin_id` live exclusively on
`BuiltinResourceDescriptor`, owned end-to-end by `BuiltinResourceService`
(`get_descriptor`, `is_builtin`, `is_visible_to`, `_set_visibility`,
`cleanup_on_delete`) and persisted via `BuiltinResourceDescriptorRepository`.
A resource with no matching descriptor is a plain custom resource. `ownership`
as a query-filter *value* (`"builtin"`/`"custom"` on `/resources.list`) and as
a serialized *response field* (via `ResourcesService.to_dict()`, stamped back
on from the descriptor) still exist — only the underlying storage model
changed, not the HTTP/JSON API contract.

Non-admin callers never see `DRAFT` built-ins — enforced at
`ResourcesService.get_visible()` (via `BuiltinResourceService.is_visible_to()`),
`BuiltinResourceService.get_builtin_schema()`/`get_user_config()`/`configure_builtin()`,
and the `builtins.list`/`get_builtin_schema` endpoints via `is_admin`.

`ResourceCategory.builtin_disabled_categories()` (currently `{RETRIEVER}`) blocks
retrievers from ever becoming built-ins — `create_builtin_with_cascade`, `promote_with_cascade`,
and the cascade-promotion helper all check this.

### Field Hints Drive Configurability & Card Display

Which config fields are user-configurable on a built-in, and which fields show
on an element's inventory card, is declared **once**, on the Pydantic config
schema, via `mas.core.field_hints` hints — never hardcoded in service/UI logic:

| Hint | Effect |
|------|--------|
| `ReadOnlyHint(read_only=False)` | Field is user-configurable on a built-in (per-identity overlay). Fields without this hint default to read-only for built-ins — see `BuiltinResourceService.get_builtin_schema()`. |
| `SecretHint` | Field is encrypted at rest (unioned with the config model's `ENCRYPTED_FIELDS`) and masked in the UI. Never rendered on a card. |
| `CardHint(contexts=[...])` | Field opts into inventory-card display, scoped to `CardContext.BUILTIN` and/or `CardContext.CUSTOM` independently — e.g. an MCP `mcp_url` is useful on a custom card, redundant on a built-in one. `empty_text` supplies a fallback when "unset" still means something (e.g. MCP `tool_names` empty ⇒ "All tools"). |

`ResourceFieldEncryption.scan_schema_hints(category, type_key)` does a single
pass over the JSON schema to return `(configurable_keys, sensitive_keys)` —
the shared source of truth consumed by `get_builtin_schema()`, `get_user_config()`,
`configure_builtin()`, and `resolve_overlay()`. On the UI side,
`lib/cardFields.ts#getCardFields()` interprets the same `hints.card`/`hints.secret`/
`hints.hidden`/`hints.conditional` structure generically — see `domains/ui/SKILL.md`.

### Per-Identity Overlay Resolution

```text
BlueprintResolver.resolve(draft, caller)
  → _ResolveSession(caller, ...)
  → _walk_live(rid, name, session)
  → ResourcesService.get_visible(rid, caller=session.caller)
  → ResourcesService.resolve_resource(resource, session.caller)
      → BuiltinResourceService.resolve_overlay(resource, caller.identity)
          → identity_to_key(identity) = "<type>:<id>"   e.g. "team:eng-42"
          → BuiltinUserConfigRepository.get(rid, key)   (one overlay doc per resource+identity)
          → decrypt configurable+sensitive fields, merge over cfg_dict
```

There is no user-over-team fallback chain — whichever `Identity` the caller is
currently operating as (their own, or a team identity in team-workspace mode)
has its own independent overlay. `caller.identity=None` (e.g. schema-only
tooling) skips overlay resolution entirely and returns raw built-in defaults —
this is also the pre-overlay behavior, so it's backward compatible.

`BlueprintService` and `BlueprintResolver` thread a single `caller: CallerScope
= CallerScope()` keyword through `load_resolved()`, `resolve_draft_dict()`,
`_resolve_doc()`, `get_resolved_doc()`, `validate_blueprint()`,
`validate_draft()`, `get_blueprint_cards()`, `get_draft_cards()` — any new
resolution/validation entrypoint on `BlueprintService` should follow this
pattern (accept and thread `caller: CallerScope = CallerScope()`) rather than
adding separate `identity`/`is_admin` parameters or a parallel built-in-aware
code path. This is exactly what makes the pattern Open/Closed: adding a new
caller attribute later only means adding a field to `CallerScope`, not
touching every method signature down the chain again.

### Cascade Promote/Demote

An "available to all" built-in (e.g. an agent) can reference other resources
(LLM, providers, tools) via `nested_refs`. Making the agent public while its
LLM is still `DRAFT` would leave end users referencing a building block they
can't see — so promotion/creation/update cascades:

- `preview_cascade_targets(rid)` — read-only BFS over `nested_refs`, returns every
  transitive dependency not already a public built-in. Used for a "these will
  also become available to all" confirmation dialog *before* mutating.
- `_cascade_promote_dependencies(rid)` — same walk, but promotes each dependency.
  Rejects the whole cascade (raises `ValueError` via `_assert_cascade_promotable()`)
  if any transitive dependency belongs to `builtin_disabled_categories()`, instead
  of skipping it — `promote_with_cascade`/`create_builtin_with_cascade`/
  `update_builtin_with_cascade` all validate/mutate in an order that keeps the
  parent non-public until this succeeds, so a rejected cascade never leaves a
  public resource referencing an invisible dependency.
- Demoting/toggling a built-in **off** is blocked with `BuiltinDependentsPublicError`
  if a public built-in still depends on it (`_find_public_dependents` — reverse BFS
  via `ResourcesRegistry.list_nested_usage()`).

Every mutation that can cascade returns a `(resource, cascaded)` tuple from a
`*_with_cascade` method — `create_builtin_with_cascade`, `promote_with_cascade`,
`update_builtin_with_cascade`, `toggle_visibility_with_cascade`. There are no
non-cascade convenience wrappers; endpoints and tests alike call the
`*_with_cascade` variants directly (discarding the second element when the
cascade list isn't needed) so behavior never silently diverges between a
"thin" and "cascading" code path.

### Authorization

`ResourcesService.guard_write_access(rid, caller)` is the single authorization
gate for resource mutation:
- Admins (`caller.is_admin`) bypass all checks.
- Built-in resources: `BuiltInWriteProtectedError` for non-admins (regular
  `resource.update`/`resource.delete` endpoints call this before mutating —
  built-ins are only mutated via the `builtins_bp` admin routes).
- Custom resources owned by a different identity (`caller.identity`):
  `ResourceAccessDeniedError`.

Admin gating itself (`is_admin`) is resolved via `AdminConfigReaderPort` →
`MongoAdminConfigReader`, which reads the **backend service's** `admin_config`
Mongo collection read-only (see `references/adapters.md` Established Patterns —
this is a deliberate, documented exception to normal per-service Mongo ownership,
not cross-service repository access). `adapters/inbound/flask/decorators.py`'s
`resolve_caller_scope(identity)` is the single place a Flask endpoint should
build the `CallerScope` from `identity` + `is_admin_user(username)`, reusing
`is_admin_user`'s per-request cache.

### Admin Edit Locks

Built-in admin editing reuses the existing team-collaboration lock
infrastructure (`CollaborationService`) with a fixed `__admin__` namespace
and a new `"builtin"` lock kind (`BUILTIN_LOCK_KIND`), instead of adding a
parallel locking mechanism:

```text
acquire_admin_edit_lock/release_admin_edit_lock/renew_admin_edit_lock/get_admin_edit_lock(s)_batch
  → CollaborationService.*_team_edit_lock(ADMIN_LOCK_NAMESPACE, "builtin", entity_id, user_id, ...)
```

No team-membership checks are needed (`@require_admin_access` at the endpoint
gates it instead). `builtin.update` and `builtin.toggle` (plus the generic
`resource.update`/`resource.delete` routes admins also use on built-ins)
call `reject_if_locked_by_other()` — the lock is a real, server-enforced
guard, not just a UI hint. `builtin.create` has no lock check (no entity id
exists yet). Note: `promote_with_cascade()` still exists as a service-layer
method (used internally by `toggle_visibility_with_cascade` when turning a
draft built-in public) — there is no dedicated `resource.promote` HTTP
endpoint; it was removed as unused (no UI caller).

### Seeding

There is no startup-time template seeding anymore — built-in resources are
created on demand via `BuiltinResourceService.create_builtin_with_cascade()`
(admin only, e.g. through the Repository Management panel), which persists
the resource under the creating admin's own identity with a random `rid`
(same as any other resource) rather than a deterministic one. New built-ins
default to `visibility=DRAFT`; an admin promotes/toggles them public
(`promote_with_cascade()` / `toggle_visibility_with_cascade()`) when ready.
(A separate, unrelated idempotent script — `multi-agent/scripts/seed_auth_servers.py`
— pre-populates the `server_configs` collection with known OAuth client
configs; it has nothing to do with the `resources` collection above.)

### Sharing Interaction

`ShareCloner` never clones built-in resources into a share — they're
"shared by reference" (the recipient resolves the same built-in at runtime,
picking up their own per-identity overlay). Any `docs_rag` retriever's `docs`
field is stripped when cloning a *non-built-in* resource across identities
(the recipient can't access the sender's document selection).

## How to Extend

### Adding a New Built-in-Eligible Element

Any element category outside `ResourceCategory.builtin_disabled_categories()`
is automatically eligible — no extra registration needed. To make new config
fields behave correctly once an instance is promoted to built-in:

1. Mark user-configurable fields with `ReadOnlyHint(read_only=False)` (all
   other fields become read-only for end users once built-in).
2. Mark fields that should show on inventory cards with `CardHint(contexts=[...])`.
3. Mark sensitive fields with `SecretHint` (encrypted at rest automatically —
   no extra wiring needed in `ResourceFieldEncryption`).
4. Add a template to `builtin_templates.py` if it should ship as a seeded default.

See `../recipes/` for the full per-element-type recipe; field hint conventions
are also summarized in `references/elements.md`.

### Adding a New Built-in Admin Operation

1. Add the method to `BuiltinResourceService` — it's the sole owner of the
   admin/overlay surface now, with no thin delegate needed on
   `ResourcesService` (that would reintroduce the pass-through methods this
   split deliberately removed).
2. Add the Flask route in `adapters/inbound/flask/endpoints/builtins.py`
   (NOT `resources.py`), calling `current_app.container.builtin_resource_service`
   directly. Serialize the returned `Resource` via
   `current_app.container.resources_service.to_dict(doc)` if the response
   needs the `ownership`/`visibility` JSON fields.
3. If it mutates an existing built-in, call `_reject_if_locked_by_other(resource_id)` first.
4. If it can affect `nested_refs` visibility, decide whether it needs cascade
   handling (`*_with_cascade` + `cascaded_resources` in the response).

## Cross-Component Contracts

### Resources → Core (Identity, Enums, Field Hints)

- `Resource.identity: Identity` — for built-ins this is the identity of the
  admin who created the resource via `create_builtin_with_cascade()` (see
  "Seeding" above); there is no separate `SYSTEM` identity type.
- `ResourceOwnership`, `ResourceVisibility` live in `mas.core.enums` alongside
  `ResourceCategory` — but `ResourceOwnership` is now only ever a query-filter
  *value* (`"builtin"`/`"custom"`) or a serialized response field, never a
  `Resource` attribute; `ResourceVisibility` lives on `BuiltinResourceDescriptor`
  (`resources/builtin_models.py`), not on `Resource`.
- Field hints (`ReadOnlyHint`, `CardHint`, `SecretHint`, ...) live in `mas.core.field_hints`.
- `CallerScope` lives in `mas.core.caller_scope` (domain layer, not Flask) —
  "who is calling and what can they see" is a domain concept threaded through
  resources/blueprints, not an HTTP-only one.

### Resources → Blueprints (Resolution)

- `BlueprintResolver` depends on the `ResourceReader` Protocol (`resources/ports.py`),
  not `ResourcesService` or `ResourcesRegistry` directly — Dependency Inversion:
  the resolver depends on an abstraction it defines the shape of, and
  `ResourcesService` happens to satisfy it structurally. This is what makes
  built-in overlay resolution transparent to blueprint resolution.
- `caller: CallerScope` flows: Flask endpoint (`resolve_caller_scope(identity)`)
  → `BlueprintService` method → `BlueprintResolver.resolve()`
  → `ResourceReader.get_visible()`/`resolve_resource()` → `BuiltinResourceService.resolve_overlay()`.

### Resources → Collaboration (Admin Locks)

- `builtins.py` endpoints reuse `CollaborationService`'s team-lock methods with
  the `ADMIN_LOCK_NAMESPACE` / `BUILTIN_LOCK_KIND` constants — see `references/session.md`
  or `CollaborationService` directly for the underlying lock TTL/store mechanics.

### Resources → Sharing (Clone Exclusion)

- `ShareCloner` checks `self.builtin.get_descriptor(rid) is not None` (a
  `BuiltinDescriptorReader`, satisfied by `BuiltinResourceService`) before
  adding a resource to a share's clone closure — built-ins are excluded, not
  cloned; a `DRAFT` built-in raises `ShareCloneError` instead (it would be
  invisible to the recipient either way).

### Machine-Checkable Invariants

| ID | Rule | Violating Pattern | Severity |
|----|------|--------------------|----------|
| INV-R01 | All resource mutation goes through `ResourcesService`/`BuiltinResourceService`, never `ResourcesRegistry` directly, from outside `lib/mas/resources/` | `from mas.resources.registry import ResourcesRegistry` in `adapters/`, other domain components, or tests exercising the public API | MAJOR |
| INV-R02 | Built-in resources are never mutated by non-admin end users | Missing `guard_write_access()` / `@require_admin_access` call on a code path that can write a `BuiltinResourceDescriptor` | CRITICAL |
| INV-R03 | Sensitive config fields (`SecretHint` or `ENCRYPTED_FIELDS`) are encrypted before persistence | `cfg_dict`/overlay `fields` assignment bypassing `ResourceFieldEncryption.encrypt_fields()`/`encrypt_config_fields()` | CRITICAL |
| INV-R04 | `Resource`/`ResourceQuery` never regain `ownership`/`visibility`/`parent_builtin_id`/`is_admin` fields | Adding those fields back onto `resources/models.py` instead of `BuiltinResourceDescriptor` | MAJOR |

## Established Patterns

These patterns are established and reviewers MUST NOT flag them as violations:

| Pattern | Where it exists | Why it's acceptable |
|---------|-----------------|---------------------|
| `ResourcesService` and `BuiltinResourceService` are two separate public facades sharing the same underlying `ResourcesRegistry`/`ResourceFieldEncryption`, rather than one large class or a strict internal-only sub-service | `resources/service.py`, `builtin_service.py`, `field_encryption.py`, `bootstrap/container.py` | "Service as Public API" is preserved for each concept separately — base CRUD callers only ever see `ResourcesService`, built-in admin/overlay callers only ever see `BuiltinResourceService`; `ResourcesService` still composes the latter internally for the few CRUD-path checks it needs, but never re-exposes its admin surface |
| `BlueprintResolver` takes a `ResourceReader` Protocol, `ShareCloner` takes `ResourceClonePort` + `BuiltinDescriptorReader` Protocols (not the full services) | `blueprints/resolver.py`, `sharing/cloner.py`, `resources/ports.py` | Dependency Inversion — each consumer depends only on the narrow slice of behavior it actually calls; `ResourcesService`/`BuiltinResourceService` satisfy these structurally, no inheritance or container changes needed |
| `caller: CallerScope = CallerScope()` threaded through resources/blueprint resolve/validate/card methods | `resources/service.py`, `blueprints/service.py`, `blueprints/resolver.py` | Backward compatible — omitting it reproduces pre-overlay, non-admin behavior; tooling that has no caller identity still works. Replaces separately threading `identity`+`is_admin` through ~15+ method signatures (Shotgun Surgery) |
| `BlueprintResolver` collapses per-call walk state into a private `_ResolveSession(caller, bucket, visited, broken_refs, strict)` dataclass instead of threading 5-8 individual parameters through `_stash_inline`/`_walk_live`/`_scan_nested` | `blueprints/resolver.py` | New per-call state (e.g. a future cycle-detection counter) is one field on `_ResolveSession`, not a new parameter on three methods |
| Admin edit locks reuse `CollaborationService`'s team-lock store with a fixed namespace (`__admin__`) and new lock kind (`"builtin"`) | `collaboration/service.py`, `endpoints/builtins.py` | Avoids a parallel locking mechanism; team-membership checks are skipped because `@require_admin_access` already gates the endpoint |
| `ResourcesService.to_dict()`/`to_dicts()` stamp `ownership`/`visibility`/`user_configured` back onto the serialized JSON by querying `BuiltinResourceService.get_descriptor()` per resource | `resources/service.py` | Preserves the existing HTTP/JSON API contract even though `Resource` itself no longer carries those fields; accepted as one lookup per resource rather than a batched/joined variant since listing endpoints already get the joined query from `BuiltinResourceDescriptorRepository.find_visible_for_identity()` |

## Change Impact

| If you change... | Also update... | Why |
|-----------------|----------------|-----|
| `ReadOnlyHint`/`CardHint`/`SecretHint` semantics | `ResourceFieldEncryption.scan_schema_hints()`, `BuiltinResourceService.get_builtin_schema()`, UI `lib/cardFields.ts` | Single hint contract consumed by both backend schema exposure and UI rendering |
| `ResourceOwnership`/`ResourceVisibility` enums or `BuiltinResourceDescriptor` shape | `BuiltinResourceDescriptorRepository` (ABC + Mongo adapter), `BuiltinResourceService` visibility checks, `builtin_disabled_categories()`, UI ownership-scoped rendering, `run/scripts/migrate_builtin_descriptors.py` | Discovery/authorization/UI/migration all branch on these values |
| `BlueprintResolver`/`BlueprintService` resolution signatures | Every caller (Flask endpoints, tests) must thread `caller: CallerScope` correctly | Built-in overlays silently fall back to raw defaults if `caller.identity` is dropped along the chain |
| `CallerScope` fields | `ResourceReader`/`ResourceClonePort`/`BuiltinDescriptorReader` Protocol signatures (`resources/ports.py`) if the new field affects what those consumers need, `resolve_caller_scope()` in `adapters/inbound/flask/decorators.py` | `CallerScope` is constructed once at the Flask boundary and passed by reference everywhere else — the boundary is the only place that needs to change to populate a new field |
| `BuiltinUserConfig` document shape | `MongoBuiltinUserConfigRepository`, `builtin_models.identity_to_key()` | Storage key format (`"<type>:<id>"`) must stay consistent between writer and reader |
| Cascade promote/demote logic | `preview_cascade_targets`, `_cascade_promote_dependencies`, `_find_public_dependents`, endpoint `cascaded_resources` reporting | All four must agree on what "transitively depends on" means |
| `ResourcesService.to_dict()`/`to_dicts()` output shape | Flask `resources.py`/`builtins.py` handlers that `jsonify()` it directly, UI `types/workspace.ts` / `resources.ts` consumers | It's the sole place the `ownership`/`visibility`/`user_configured` JSON contract is assembled now that `Resource` doesn't carry those fields |

## Boundaries

**Owns:** resource CRUD, validation delegation, card building, built-in admin lifecycle
(create/promote/demote/toggle/cascade), per-identity built-in overlays, field encryption
for resource configs, blueprint draft/spec resolution.
**Does NOT own:** element implementations or schemas (elements owns those; resources only
stores/validates against them), session execution (session), identity resolution (core).
