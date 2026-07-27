"""Built-in resource lifecycle: admin CRUD, schema exposure, and per-identity
configuration overlays.

Split out of ``ResourcesService`` (which had grown to own base CRUD,
validation, card building, *and* the entire built-in admin/overlay
lifecycle) so each service stays within a single responsibility. This is an
internal collaborator, not an independent public API: external callers
(Flask endpoints, ``BlueprintResolver``, tests) go through
``ResourcesService``, which composes this class and delegates its built-in
methods to it — the "Service as Public API" pattern is preserved at the
``ResourcesService`` facade.
"""
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import ValidationError as PydanticValidationError

from mas.core.identity import Identity
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.ref import RefWalker
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.resources.builtin_models import BuiltinUserConfig, identity_to_key
from mas.resources.errors import BuiltinConfigUnavailableError, BuiltinDependentsPublicError
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.catalog.element_registry import ElementRegistry

logger = logging.getLogger(__name__)

# Hidden fields that the auth/validation layer writes automatically (e.g.
# ``McpProviderConfig.server_identifier`` / ``scheme_type``, populated by
# ``auth.discovery`` once a sign-in flow resolves the real OAuth issuer).
# They carry ``HiddenHint`` rather than ``ReadOnlyHint(read_only=False)``, so
# they're intentionally excluded from ``scan_schema_hints``'s configurable
# set — but a signed-in built-in resource still needs them persisted onto
# its per-identity overlay, or every later validation falls back to an
# unauthenticated probe against a stale/empty identifier. Mirrors the
# equivalent special case in ``ElementForm.tsx`` for regular (non-builtin)
# resources, which always includes these two hidden fields in its save
# payload for the same reason.
AUTH_METADATA_OVERLAY_FIELDS = frozenset({"server_identifier", "scheme_type"})


class BuiltinResourceService:
    """Admin lifecycle + per-identity overlays for built-in resources."""

    def __init__(
        self,
        resource_registry: ResourcesRegistry,
        element_registry: ElementRegistry,
        field_encryption: ResourceFieldEncryption,
        builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
    ) -> None:
        self._store = resource_registry
        self.element_registry = element_registry
        self._fields = field_encryption
        self._builtin_user_config_repo = builtin_user_config_repo

    def _auth_metadata_keys(self, resource: Resource) -> set:
        """Auth-metadata fields that actually exist on this element's schema."""
        try:
            schema = self.element_registry.get_schema_json(
                ResourceCategory(resource.category), resource.type
            )
        except KeyError:
            return set()
        return AUTH_METADATA_OVERLAY_FIELDS & schema.get("properties", {}).keys()

    # ---------- Listing / schema ----------

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Resource]:
        """Return all built-in resources (public and draft), for admin listing."""
        return self._store.find_all_builtins(category=category, resource_type=type)

    def get_builtin_schema(self, rid: str, *, is_admin: bool = False) -> dict:
        """Return the element JSON schema with readOnly annotations for a built-in resource.

        Reads ReadOnlyHint from the Pydantic schema to determine which fields
        are configurable. Non-configurable visible fields get ``read_only: true`` added.
        Draft built-ins are only accessible to admins.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if (
            resource.visibility != ResourceVisibility.PUBLIC
            and not is_admin
        ):
            raise KeyError(rid)

        schema = self.element_registry.get_schema_json(
            ResourceCategory(resource.category), resource.type
        )

        configurable_names, _ = self._fields.scan_schema_hints(resource.category, resource.type)

        for field_name, field_schema in schema.get("properties", {}).items():
            hints = field_schema.get("hints", {})
            if "hidden" in hints:
                continue
            if field_name not in configurable_names:
                hints["read_only"] = {"read_only": True}
                field_schema["hints"] = hints

        return schema

    # ---------- Per-identity overlays ----------

    def get_user_config(
        self,
        rid: str,
        identity: Identity,
    ) -> Dict[str, Any] | None:
        """Return the user's current overlay for a built-in resource, or None.

        Decrypts sensitive fields so the UI can display masked values.
        Only returns fields that are marked as user-configurable.
        Draft built-ins are not configurable by end users.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if resource.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        if not self._builtin_user_config_repo:
            return None

        key = identity_to_key(identity)
        user_config = self._builtin_user_config_repo.get(rid, key)
        if not user_config:
            return None

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type
        )
        filtered = {k: v for k, v in user_config.fields.items() if k in configurable_keys}
        return self._fields.decrypt_config_fields(filtered, sensitive_keys, model_cls)

    def configure_builtin(
        self,
        rid: str,
        identity: Identity,
        config: Dict[str, Any],
    ) -> Resource:
        """Save per-user/team configuration for a built-in resource.

        Allowed fields are determined by ReadOnlyHint annotations on the element schema.
        Draft built-ins are not configurable by end users.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if resource.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        allowed_keys = configurable_keys | self._auth_metadata_keys(resource)
        if not allowed_keys:
            raise ValueError("No configurable fields defined for this element type")

        filtered = {k: v for k, v in config.items() if k in allowed_keys}
        if not filtered:
            raise ValueError("No valid configurable fields provided")

        if not self._builtin_user_config_repo:
            raise BuiltinConfigUnavailableError()

        # Validate the overlay against the element's Pydantic model before
        # persisting, the same way ResourcesService.create()/update_builtin()
        # validate cfg_dict. Merge onto the (decrypted) base config first so
        # cross-field constraints see the complete picture, then re-extract
        # only the overridden keys from the validated/coerced output — this
        # ensures invalid values are rejected here instead of silently
        # persisting and only surfacing later at resolve() time.
        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type
        )
        base_config = self._store.raw_config(rid)
        merged = {**base_config, **filtered}
        try:
            cfg_model = model_cls(**merged)
        except PydanticValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        validated_dump = cfg_model.model_dump(mode="json")
        validated = {k: validated_dump[k] for k in filtered if k in validated_dump}

        encrypted = self._fields.encrypt_config_fields(validated, sensitive_keys, model_cls)

        key = identity_to_key(identity)
        existing = self._builtin_user_config_repo.get(rid, key)
        if existing:
            existing.fields.update(encrypted)
            self._builtin_user_config_repo.save(existing)
        else:
            user_config = BuiltinUserConfig(
                resource_id=rid,
                identity_key=key,
                fields=encrypted,
            )
            self._builtin_user_config_repo.save(user_config)

        logger.info("Built-in resource '%s' configured for %s", rid, key)
        return resource

    def strip_unconfigured_secrets(
        self, resource: Resource, config: dict[str, Any],
    ) -> dict[str, Any]:
        """Remove per-user secret values from a built-in's shared base config.

        Fields that are both user-configurable (``ReadOnlyHint(read_only=False)``)
        and sensitive (``SecretHint``) — e.g. an MCP ``bearer_token`` — are meant
        to come exclusively from the caller's own overlay (``resolve_overlay``),
        never from the resource's shared ``cfg_dict``. Without this, a value an
        admin happened to save on the base config (e.g. while testing
        connectivity before promoting it) would silently leak to every other
        user who never configured their own credential, making that user's
        resource appear "valid" while actually authenticating as the admin.

        Called before merging the overlay in ``ResourcesService.resolve()`` so
        a caller with their own overlay value still gets it (the overlay merge
        happens after this), while a caller without one gets the field's
        schema default (``None``/empty) instead of the admin's value.
        """
        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        secret_configurable_keys = configurable_keys & sensitive_keys
        if not secret_configurable_keys:
            return config
        stripped = dict(config)
        for key in secret_configurable_keys:
            stripped.pop(key, None)
        return stripped

    def find_missing_required_overlay_fields(
        self, resource: Resource, resolved_config: Any,
    ) -> list[str]:
        """Secret+configurable fields still empty after overlay resolution.

        Combined with ``strip_unconfigured_secrets``, an empty value on
        *resolved_config* for one of these fields means this caller's
        identity has no overlay of their own providing it — e.g. an MCP
        ``bearer_token`` when ``auth_method`` is set to access-token auth.
        Without an explicit check, that empty credential just gets handed
        to the element's validator, which may probe the connection anyway
        and — if the server happens to tolerate unauthenticated requests —
        incorrectly report the resource as valid for a user who never
        configured anything.

        ``ConditionalHint`` scopes the check to fields actually relevant to
        *resolved_config* (e.g. a ``sign_in``-mode MCP never requires
        ``bearer_token``, so it's skipped rather than always demanded).
        """
        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        secret_configurable_keys = configurable_keys & sensitive_keys
        if not secret_configurable_keys:
            return []

        try:
            schema = self.element_registry.get_schema_json(
                ResourceCategory(resource.category), resource.type
            )
        except KeyError:
            return []
        properties = schema.get("properties", {})

        missing = []
        for key in sorted(secret_configurable_keys):
            conditional = (
                properties.get(key, {}).get("hints", {}).get("conditional", {}).get("visible_when")
            )
            if conditional and not all(
                getattr(resolved_config, field_name, None) == value
                for field_name, value in conditional.items()
            ):
                continue
            if not getattr(resolved_config, key, None):
                missing.append(key)
        return missing

    def resolve_overlay(self, resource: Resource, identity: Identity) -> Dict[str, Any]:
        """Resolve the effective config overlay for a built-in resource.

        Used by ``ResourcesService.resolve()`` to merge a caller's overlay
        into the resource's base config at runtime.

        Uses ReadOnlyHint from the Pydantic schema to identify configurable
        fields, then looks up the single overlay document keyed by
        ``identity_to_key(identity)`` — i.e. whichever identity the caller
        is currently operating as (their own user identity, or a team
        identity when acting in a team workspace). There is no separate
        user-over-team fallback chain: each identity has its own
        independent overlay. Decrypts sensitive fields before returning.

        Fields absent from the user config are not included — the caller will
        keep the resource's ``cfg_dict`` value for those.
        """
        if not self._builtin_user_config_repo:
            return {}

        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        allowed_keys = configurable_keys | self._auth_metadata_keys(resource)
        if not allowed_keys:
            return {}

        key = identity_to_key(identity)
        user_config = self._builtin_user_config_repo.get(resource.rid, key)
        if not user_config:
            return {}

        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type
        )
        overlay = {k: v for k, v in user_config.fields.items() if k in allowed_keys}
        return self._fields.decrypt_config_fields(overlay, sensitive_keys, model_cls)

    # ---------- Admin lifecycle ----------

    def duplicate_builtin(
        self,
        rid: str,
        identity: Identity,
        name: str,
        config_overrides: Dict[str, Any] = None,
    ) -> Resource:
        """Clone a built-in resource into a custom resource."""
        source = self._store.get(rid)
        if source.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        if source.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(rid)

        # cfg_dict may contain encrypted sensitive fields — decrypt before
        # merging overrides so the merge operates on plaintext, then
        # re-encrypt the merged result. Encrypting without decrypting first
        # would double-encrypt already-ciphertext values and corrupt them.
        merged_config = self._store.raw_config(rid)
        if config_overrides:
            merged_config.update(config_overrides)

        model_cls = self.element_registry.get_schema(
            ResourceCategory(source.category), source.type)
        cfg_model = model_cls(**merged_config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls,
            category=source.category, type_key=source.type,
        )

        doc = Resource(
            rid=uuid4().hex,
            identity=identity,
            category=source.category,
            type=source.type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
            ownership=ResourceOwnership.CUSTOM,
            parent_builtin_id=source.rid,
        )
        return self._store.create(doc)

    def create_builtin(
        self,
        *,
        identity: Identity,
        category: str,
        type: str,
        name: str,
        config: dict,
        available_to_all: bool = False,
    ) -> Resource:
        """Create a resource directly as built-in (admin only).

        See ``create_builtin_with_cascade`` for the cascading behavior.
        """
        resource, _ = self.create_builtin_with_cascade(
            identity=identity, category=category, type=type, name=name,
            config=config, available_to_all=available_to_all,
        )
        return resource

    def create_builtin_with_cascade(
        self,
        *,
        identity: Identity,
        category: str,
        type: str,
        name: str,
        config: dict,
        available_to_all: bool = False,
    ) -> "tuple[Resource, List[Resource]]":
        """Create a resource directly as built-in (admin only).

        The identity of the creating admin is preserved so that every
        built-in resource document is owned by the admin who created it,
        keeping the identity consistent across all documents in the
        resources collection.

        Configurable fields are determined by ReadOnlyHint annotations on
        the element schema. If ``available_to_all`` is set and the config
        references other resources (e.g. an agent's LLM/provider/tool refs)
        that aren't already public built-ins, those are promoted alongside
        it — the second tuple element lists exactly what got cascaded.
        """
        cat_enum = ResourceCategory(category)
        if cat_enum in ResourceCategory.builtin_disabled_categories():
            raise ValueError(
                f"Category '{category}' is not supported for built-in resources"
            )

        model_cls = self.element_registry.get_schema(ResourceCategory(category), type)
        cfg_model = model_cls(**config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls, category=category, type_key=type
        )

        doc = Resource(
            identity=identity,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
            ownership=ResourceOwnership.BUILTIN,
            visibility=ResourceVisibility.PUBLIC if available_to_all else ResourceVisibility.DRAFT,
        )
        created = self._store.create(doc)
        cascaded = self._cascade_promote_dependencies(created.rid) if available_to_all else []
        return created, cascaded

    def promote(self, rid: str) -> Resource:
        """Make a resource a public built-in (admin only).

        See ``promote_with_cascade`` for the cascading behavior.
        """
        resource, _ = self.promote_with_cascade(rid)
        return resource

    def promote_with_cascade(self, rid: str) -> "tuple[Resource, List[Resource]]":
        """Make a resource a public built-in (admin only).

        Accepts a custom resource (promotes to builtin + public) or an
        existing draft built-in (sets visibility to public). The original
        identity is preserved so API-created resources keep their admin owner.

        Cascades: any element this resource aggregates (LLMs, providers,
        tools, etc. referenced via ``nested_refs``) that isn't already a
        public built-in gets promoted too, so an "available to all" agent
        never ends up referencing a building block hidden from end users.
        Returns ``(resource, cascaded)`` where ``cascaded`` lists exactly
        what got swept along, for the caller to surface a disclaimer.
        """
        resource = self._store.get(rid)
        if resource.ownership not in (
            ResourceOwnership.CUSTOM,
            ResourceOwnership.BUILTIN,
        ):
            raise ValueError(
                f"Cannot promote resource with ownership '{resource.ownership}'"
            )
        cat_enum = ResourceCategory(resource.category)
        if cat_enum in ResourceCategory.builtin_disabled_categories():
            raise ValueError(
                f"Category '{resource.category}' is not supported for built-in resources"
            )
        resource.ownership = ResourceOwnership.BUILTIN
        resource.visibility = ResourceVisibility.PUBLIC
        updated = self._store.update(resource)
        cascaded = self._cascade_promote_dependencies(rid)
        return updated, cascaded

    def demote(self, rid: str) -> Resource:
        """Demote a public built-in to draft (admin-only visibility).

        Blocked with ``BuiltinDependentsPublicError`` when another public
        built-in still aggregates this resource (e.g. an "available to all"
        agent that uses this LLM/provider/tool) — otherwise that agent would
        be left referencing a building block end users can no longer see.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")
        self._ensure_no_public_dependents(resource)
        resource.visibility = ResourceVisibility.DRAFT
        return self._store.update(resource)

    # ---------- Nested-dependency cascade helpers ----------

    def preview_cascade_targets(self, rid: str) -> List[Resource]:
        """Resources that would be newly promoted if *rid* were promoted.

        Walks ``nested_refs`` transitively (LLMs, providers, tools, etc.
        aggregated by an agent/node) and returns every dependency that
        isn't already a public built-in. Read-only — used to build the
        "these will also be made available to all" disclaimer before/while
        toggling a resource on.
        """
        return [
            dep for dep in self._iter_transitive_deps(rid)
            if not (
                dep.ownership == ResourceOwnership.BUILTIN
                and dep.visibility == ResourceVisibility.PUBLIC
            )
        ]

    def _cascade_promote_dependencies(self, rid: str) -> List[Resource]:
        """Promote every not-yet-public transitive dependency of *rid*."""
        promoted: List[Resource] = []
        for dep in self.preview_cascade_targets(rid):
            cat_enum = ResourceCategory(dep.category)
            if cat_enum in ResourceCategory.builtin_disabled_categories():
                logger.warning(
                    "Skipping cascade promotion of '%s': category '%s' is "
                    "not supported for built-in resources", dep.rid, dep.category,
                )
                continue
            dep.ownership = ResourceOwnership.BUILTIN
            dep.visibility = ResourceVisibility.PUBLIC
            self._store.update(dep)
            promoted.append(dep)
        return promoted

    def _iter_transitive_deps(self, rid: str) -> List[Resource]:
        """All resources transitively referenced by *rid* via ``nested_refs``
        (breadth-first, excludes *rid* itself, no duplicates)."""
        visited = {rid}
        result: List[Resource] = []
        queue = [rid]
        while queue:
            current = queue.pop(0)
            try:
                resource = self._store.get(current)
            except KeyError:
                continue
            for dep_rid in resource.nested_refs:
                if dep_rid in visited:
                    continue
                visited.add(dep_rid)
                try:
                    dep = self._store.get(dep_rid)
                except KeyError:
                    continue
                result.append(dep)
                queue.append(dep_rid)
        return result

    def _ensure_no_public_dependents(self, resource: Resource) -> None:
        """Raise if any public built-in still aggregates *resource*."""
        dependents = self._find_public_dependents(resource.rid)
        if dependents:
            raise BuiltinDependentsPublicError(
                resource_name=resource.name,
                category=str(resource.category.value if hasattr(resource.category, "value") else resource.category),
                dependents=dependents,
            )

    def _find_public_dependents(self, rid: str) -> List[Resource]:
        """All resources that transitively depend on *rid* (directly or via
        a chain of ``nested_refs``) and are themselves public built-ins."""
        visited = {rid}
        result: List[Resource] = []
        queue = [rid]
        while queue:
            current = queue.pop(0)
            for parent_rid in self._store.list_nested_usage(current):
                if parent_rid in visited:
                    continue
                visited.add(parent_rid)
                try:
                    parent = self._store.get(parent_rid)
                except KeyError:
                    continue
                if (
                    parent.ownership == ResourceOwnership.BUILTIN
                    and parent.visibility == ResourceVisibility.PUBLIC
                ):
                    result.append(parent)
                queue.append(parent_rid)
        return result

    def update_builtin(
        self,
        rid: str,
        *,
        config: dict = None,
        name: str = None,
        available_to_all: bool = None,
    ) -> Resource:
        """Update a built-in resource (admin only).

        See ``update_builtin_with_cascade`` for the cascading behavior.
        """
        resource, _ = self.update_builtin_with_cascade(
            rid, config=config, name=name, available_to_all=available_to_all,
        )
        return resource

    def update_builtin_with_cascade(
        self,
        rid: str,
        *,
        config: dict = None,
        name: str = None,
        available_to_all: bool = None,
    ) -> "tuple[Resource, List[Resource]]":
        """Update a built-in resource (admin only).

        Allows updating config, name, and visibility. Turning
        ``available_to_all`` on cascades to any not-yet-public aggregated
        elements (computed *after* the config update, so it reflects any
        newly-added refs) — the second tuple element lists what got
        cascaded. Turning it off is rejected with
        ``BuiltinDependentsPublicError`` if a public built-in still
        aggregates this resource.
        """
        resource = self._store.get(rid)
        if resource.ownership != ResourceOwnership.BUILTIN:
            raise ValueError("Resource is not a built-in resource")

        if config is not None:
            model_cls = self.element_registry.get_schema(
                ResourceCategory(resource.category), resource.type)
            cfg_model = model_cls(**config)
            resource.cfg_dict = self._fields.encrypt_fields(
                cfg_model.model_dump(mode="json"), model_cls,
                category=resource.category, type_key=resource.type,
            )
            resource.nested_refs = list(RefWalker.external_rids(cfg_model))

        if name is not None:
            resource.name = name

        if available_to_all is not None:
            if available_to_all:
                resource.visibility = ResourceVisibility.PUBLIC
            else:
                if resource.visibility == ResourceVisibility.PUBLIC:
                    self._ensure_no_public_dependents(resource)
                resource.visibility = ResourceVisibility.DRAFT

        updated = self._store.update(resource)
        cascaded = self._cascade_promote_dependencies(rid) if available_to_all else []
        return updated, cascaded

    def toggle_visibility(self, rid: str, *, available_to_all: bool) -> Resource:
        """Set visibility of a built-in resource (admin only)."""
        resource, _ = self.toggle_visibility_with_cascade(rid, available_to_all=available_to_all)
        return resource

    def toggle_visibility_with_cascade(
        self, rid: str, *, available_to_all: bool,
    ) -> "tuple[Resource, List[Resource]]":
        """Set visibility of a built-in resource (admin only).

        See ``promote_with_cascade`` / ``demote`` for the cascading and
        guard behavior. Returns ``(resource, cascaded)``.
        """
        if available_to_all:
            return self.promote_with_cascade(rid)
        return self.demote(rid), []
