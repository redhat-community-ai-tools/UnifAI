"""Built-in resource lifecycle: descriptor CRUD, visibility gating, per-identity
configuration overlays, and admin cascade promote/demote.

Split out of ``ResourcesService`` (which had grown to own base CRUD,
validation, card building, *and* the entire built-in admin/overlay
lifecycle) so each service stays within a single responsibility. Unlike the
original split, this is now a **peer service**, not an internal-only
collaborator: ``builtins.py`` injects it directly for the admin/overlay
surface, while ``ResourcesService`` composes it only for the small set of
generic-CRUD helper methods it needs (``get_descriptor``, ``is_builtin``,
``resolve_config``, ``validation_override_error``, ``cleanup_on_delete``) —
see ``resources.md`` for the up-to-date architecture description.

Existence of a ``BuiltinResourceDescriptor`` for a given ``rid`` *is* the
"this resource is a built-in" signal — there is no ``ownership`` field on
``Resource`` to check anymore.
"""
import logging
from collections import deque
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ValidationError as PydanticValidationError

from mas.core.identity import Identity
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.ref import RefWalker
from mas.resources.models import Resource
from mas.resources.registry import ResourcesRegistry
from mas.resources.builtin_models import (
    BuiltinResourceDescriptor,
    BuiltinUpdateRequest,
    BuiltinUserConfig,
    identity_to_key,
)
from mas.resources.errors import BuiltinConfigUnavailableError, BuiltinDependentsPublicError
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.repository.builtin_resource_descriptor_repository import (
    BuiltinResourceDescriptorRepository,
)
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
    """Descriptor lifecycle + admin CRUD + per-identity overlays for built-ins."""

    def __init__(
        self,
        resource_registry: ResourcesRegistry,
        element_registry: ElementRegistry,
        field_encryption: ResourceFieldEncryption,
        descriptor_repo: BuiltinResourceDescriptorRepository,
        builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
    ) -> None:
        self._store = resource_registry
        self.element_registry = element_registry
        self._fields = field_encryption
        self._descriptor_repo = descriptor_repo
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

    # ---------- Core built-in-awareness (used by ResourcesService) ----------

    def get_descriptor(self, rid: str) -> Optional[BuiltinResourceDescriptor]:
        """Return the built-in descriptor for *rid*, or ``None`` if it's not a built-in."""
        return self._descriptor_repo.get(rid)

    def is_builtin(self, rid: str) -> bool:
        """Whether *rid* is a built-in resource (has a descriptor)."""
        return self.get_descriptor(rid) is not None

    def is_visible_to(self, rid: str, is_admin: bool) -> bool:
        """Draft-gate: whether *rid* is visible to a caller with *is_admin*.

        Non-built-ins are always "visible" from this method's perspective
        (the draft-gate simply doesn't apply) — callers combine this with
        their own identity-ownership checks for custom resources.
        """
        descriptor = self.get_descriptor(rid)
        if descriptor is None:
            return True
        return is_admin or descriptor.visibility == ResourceVisibility.PUBLIC

    def resolve_config(
        self, resource: Resource, base_config: Dict[str, Any], identity: Optional[Identity],
    ) -> Dict[str, Any]:
        """Merge a caller's per-identity overlay into *base_config*.

        No-ops (returns *base_config* unchanged) for non-builtins or when
        *identity* is unset — see ``strip_unconfigured_secrets``/
        ``resolve_overlay`` for why a caller-supplied credential must
        always win over the resource's shared base value.
        """
        if identity is None or not self.is_builtin(resource.rid):
            return base_config
        config = self.strip_unconfigured_secrets(resource, base_config)
        overlay = self.resolve_overlay(resource, identity)
        if overlay:
            config.update(overlay)
        return config

    def validation_override_error(
        self, resource: Resource, config: BaseModel, identity: Optional[Identity],
    ) -> Optional[str]:
        """Human-readable validation-blocking error for a built-in missing a
        required per-identity secret, or ``None`` if validation may proceed.

        No-ops for non-builtins or when *identity* is unset — see
        ``find_missing_required_overlay_fields`` for the underlying check.
        """
        if identity is None or not self.is_builtin(resource.rid):
            return None
        missing = self.find_missing_required_overlay_fields(resource, config)
        if not missing:
            return None
        return (
            f"Requires your own {', '.join(missing)} — configure it for "
            f"'{resource.name}' in your inventory before it can be validated."
        )

    def _set_visibility(self, rid: str, visibility: ResourceVisibility) -> BuiltinResourceDescriptor:
        """Create or update the descriptor for *rid* with the given visibility.

        Preserves ``created``/other fields on an existing descriptor rather
        than overwriting them, so admin promote/demote/cascade cycles don't
        reset the descriptor's creation timestamp each time.
        """
        descriptor = self.get_descriptor(rid) or BuiltinResourceDescriptor(rid=rid)
        descriptor.visibility = visibility
        self._descriptor_repo.save(descriptor)
        return descriptor

    def cleanup_on_delete(self, rid: str) -> None:
        """Purge built-in-specific state for a resource being deleted.

        No-ops for non-builtins. Removes the descriptor itself (so it
        doesn't outlive the ``Resource`` it describes) and any per-identity
        overlays.
        """
        if not self.is_builtin(rid):
            return
        self._descriptor_repo.delete(rid)
        if self._builtin_user_config_repo:
            self._builtin_user_config_repo.delete_all_for_resource(rid)

    # ---------- Listing / schema ----------

    def find_visible(
        self,
        *,
        identity: Optional[Identity],
        category: Optional[str],
        resource_type: Optional[str],
        ownership: Optional[str],
        is_admin: bool,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
    ) -> "tuple[List[Resource], int]":
        """Paginated resources visible to *identity*, merging built-in
        descriptor metadata with the base ``resources`` collection.

        Backs ``ResourcesService.find_resources()`` (the generic
        ``/resources.list`` listing) — *ownership* is the raw query-string
        filter value ("builtin"/"custom"/``None``); this is the only place
        that needs to know it maps onto ``ResourceOwnership``, so
        ``ResourcesService`` itself stays free of that enum. Raises
        ``ValueError`` for an unrecognized *ownership* string. See
        ``BuiltinResourceDescriptorRepository.find_visible_for_identity``
        for the three ``ownership`` modes.
        """
        ownership_enum = ResourceOwnership(ownership) if ownership else None
        return self._descriptor_repo.find_visible_for_identity(
            identity=identity,
            category=category,
            resource_type=resource_type,
            ownership=ownership_enum,
            is_admin=is_admin,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
        )

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> List[Resource]:
        """Return all built-in resources (public and draft), for admin listing."""
        return self._descriptor_repo.find_all_builtins(category=category, resource_type=resource_type)

    def get_builtin_schema(self, rid: str, *, is_admin: bool = False) -> dict:
        """Return the element JSON schema with readOnly annotations for a built-in resource.

        Reads ReadOnlyHint from the Pydantic schema to determine which fields
        are configurable. Non-configurable visible fields get ``read_only: true`` added.
        Draft built-ins are only accessible to admins.
        """
        resource = self._store.get(rid)
        descriptor = self.get_descriptor(rid)
        if descriptor is None:
            raise ValueError("Resource is not a built-in resource")
        if descriptor.visibility != ResourceVisibility.PUBLIC and not is_admin:
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
        Returns fields marked as user-configurable, plus any auth-metadata
        fields (``AUTH_METADATA_OVERLAY_FIELDS``) present on this identity's
        overlay — mirrors the ``allowed_keys`` set ``configure_builtin()``
        writes with, so a signed-in resource's discovered
        ``server_identifier``/``scheme_type`` actually round-trips back to
        the UI instead of silently vanishing after being persisted (leaving
        later hidden validations to fall back to an unauthenticated probe
        against a stale/empty identifier, per the comment on
        ``AUTH_METADATA_OVERLAY_FIELDS``).
        Draft built-ins are not configurable by end users.
        """
        resource = self._store.get(rid)
        descriptor = self.get_descriptor(rid)
        if descriptor is None:
            raise ValueError("Resource is not a built-in resource")
        if descriptor.visibility != ResourceVisibility.PUBLIC:
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
        allowed_keys = configurable_keys | self._auth_metadata_keys(resource)
        filtered = {k: v for k, v in user_config.fields.items() if k in allowed_keys}
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
        descriptor = self.get_descriptor(rid)
        if descriptor is None:
            raise ValueError("Resource is not a built-in resource")
        if descriptor.visibility != ResourceVisibility.PUBLIC:
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
        # validate cfg_dict. Merge onto the (decrypted) base config, then the
        # caller's *existing* overlay (so unrelated fields already configured
        # by this identity survive validation), then the newly-filtered
        # values last so they win — this ensures cross-field constraints see
        # the complete *effective* configuration, not just the base plus
        # this call's fields, and re-extract only the overridden keys from
        # the validated/coerced output so invalid values are rejected here
        # instead of silently persisting and only surfacing later at
        # resolve() time.
        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type
        )
        key = identity_to_key(identity)
        existing = self._builtin_user_config_repo.get(rid, key)

        base_config = self._store.raw_config(rid)
        existing_fields = {}
        if existing:
            existing_fields = self._fields.decrypt_config_fields(
                {k: v for k, v in existing.fields.items() if k in allowed_keys},
                sensitive_keys, model_cls,
            )
        merged = {**base_config, **existing_fields, **filtered}
        try:
            cfg_model = model_cls(**merged)
        except PydanticValidationError as e:
            raise ValueError(f"Invalid configuration: {e}") from e
        validated_dump = cfg_model.model_dump(mode="json")
        validated = {k: validated_dump[k] for k in filtered if k in validated_dump}

        encrypted = self._fields.encrypt_config_fields(validated, sensitive_keys, model_cls)

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

        Called before merging the overlay in ``resolve_config`` so a caller
        with their own overlay value still gets it (the overlay merge happens
        after this), while a caller without one gets the field's schema
        default (``None``/empty) instead of the admin's value.
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
        self, resource: Resource, resolved_config: BaseModel,
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

        Delegates the actual schema/``visible_when`` walk to
        ``ResourceFieldEncryption.find_missing_conditionally_required_secrets``
        (shared with the equivalent custom-resource check), scoped to this
        resource's configurable-and-secret fields and treating a candidate
        with no ``ConditionalHint`` as always relevant (unlike the plain
        custom-resource behavior) — see that method's docstring for why.
        """
        configurable_keys, sensitive_keys = self._fields.scan_schema_hints(
            resource.category, resource.type
        )
        secret_configurable_keys = configurable_keys & sensitive_keys
        if not secret_configurable_keys:
            return []

        return self._fields.find_missing_conditionally_required_secrets(
            resource.category,
            resource.type,
            resolved_config,
            candidate_keys=secret_configurable_keys,
            require_unconditional=True,
        )

    def resolve_overlay(self, resource: Resource, identity: Identity) -> Dict[str, Any]:
        """Resolve the effective config overlay for a built-in resource.

        Used by ``resolve_config`` to merge a caller's overlay into the
        resource's base config at runtime.

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

    def create_builtin_with_cascade(
        self,
        *,
        identity: Identity,
        category: str,
        resource_type: str,
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

        model_cls = self.element_registry.get_schema(ResourceCategory(category), resource_type)
        cfg_model = model_cls(**config)
        nested_refs = list(RefWalker.external_rids(cfg_model))
        cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls, category=category, type_key=resource_type
        )

        doc = Resource(
            identity=identity,
            category=category,
            type=resource_type,
            name=name,
            cfg_dict=cfg_dict,
            nested_refs=nested_refs,
        )
        created = self._store.create(doc)
        self._set_visibility(created.rid, ResourceVisibility.DRAFT)

        cascaded: List[Resource] = []
        if available_to_all:
            cascaded = self._cascade_promote_dependencies(created.rid)
            self._set_visibility(created.rid, ResourceVisibility.PUBLIC)
        return created, cascaded

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
        cat_enum = ResourceCategory(resource.category)
        if cat_enum in ResourceCategory.builtin_disabled_categories():
            raise ValueError(
                f"Category '{resource.category}' is not supported for built-in resources"
            )
        # Validate before mutating anything: a transitive dependency that
        # can never become a built-in (e.g. a retriever) must block the
        # whole promotion rather than being silently skipped — otherwise
        # `resource` would end up public while referencing something end
        # users can't see.
        self._assert_cascade_promotable(rid)

        self._set_visibility(rid, ResourceVisibility.DRAFT)
        cascaded = self._cascade_promote_dependencies(rid)
        self._set_visibility(rid, ResourceVisibility.PUBLIC)
        return resource, cascaded

    def demote(self, rid: str) -> Resource:
        """Demote a public built-in to draft (admin-only visibility).

        Blocked with ``BuiltinDependentsPublicError`` when another public
        built-in still aggregates this resource (e.g. an "available to all"
        agent that uses this LLM/provider/tool) — otherwise that agent would
        be left referencing a building block end users can no longer see.
        """
        resource = self._store.get(rid)
        if self.get_descriptor(rid) is None:
            raise ValueError("Resource is not a built-in resource")
        self._ensure_no_public_dependents(resource)
        self._set_visibility(rid, ResourceVisibility.DRAFT)
        return resource

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
            if not self._is_public_builtin(dep.rid)
        ]

    def _is_public_builtin(self, rid: str) -> bool:
        descriptor = self.get_descriptor(rid)
        return descriptor is not None and descriptor.visibility == ResourceVisibility.PUBLIC

    def _assert_cascade_promotable(self, rid: str) -> None:
        """Raise if cascade-promoting *rid*'s dependencies would require
        promoting one from a disabled category (e.g. a retriever).

        Read-only — callers run this before mutating *rid* itself so a
        rejected cascade never leaves *rid* public while referencing a
        dependency end users can't see (see ``builtin_disabled_categories()``).
        """
        for dep in self.preview_cascade_targets(rid):
            if ResourceCategory(dep.category) in ResourceCategory.builtin_disabled_categories():
                raise ValueError(
                    f"Cannot make this resource available to all: dependency "
                    f"'{dep.name}' ({dep.category}) is not supported as a "
                    f"built-in resource."
                )

    def _cascade_promote_dependencies(self, rid: str) -> List[Resource]:
        """Promote every not-yet-public transitive dependency of *rid*.

        Raises ``ValueError`` (via ``_assert_cascade_promotable``) instead
        of skipping-and-continuing when a dependency belongs to a disabled
        category — the parent must not end up public while referencing a
        dependency that can never become visible to end users.

        On partial failure (a mid-loop ``_descriptor_repo.save`` raises),
        all already-promoted dependencies are reverted to their
        pre-promotion state before re-raising — mirroring the rollback
        pattern in ``ShareCloner._batch_create_resources``.
        """
        self._assert_cascade_promotable(rid)
        targets = self.preview_cascade_targets(rid)
        originals: List[tuple[str, Optional[BuiltinResourceDescriptor]]] = []
        promoted: List[Resource] = []
        try:
            for dep in targets:
                orig_descriptor = self.get_descriptor(dep.rid)
                originals.append((dep.rid, orig_descriptor))
                self._set_visibility(dep.rid, ResourceVisibility.PUBLIC)
                promoted.append(dep)
        except Exception:
            logger.exception(
                "Cascade promotion failed after promoting %d of %d "
                "dependencies of '%s'; rolling back promoted deps",
                len(promoted), len(targets), rid,
            )
            for dep_rid, orig_descriptor in reversed(originals):
                try:
                    if orig_descriptor is None:
                        self._descriptor_repo.delete(dep_rid)
                    else:
                        self._descriptor_repo.save(orig_descriptor)
                except Exception:
                    logger.exception(
                        "Failed to roll back promoted dependency '%s' — it may "
                        "be left as PUBLIC and require manual cleanup", dep_rid,
                    )
            raise
        return promoted

    def _iter_transitive_deps(self, rid: str) -> List[Resource]:
        """All resources transitively referenced by *rid* via ``nested_refs``
        (breadth-first, excludes *rid* itself, no duplicates)."""
        visited = {rid}
        result: List[Resource] = []
        q: deque[str] = deque([rid])
        while q:
            current = q.popleft()
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
                q.append(dep_rid)
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
        q: deque[str] = deque([rid])
        while q:
            current = q.popleft()
            for parent_rid in self._store.list_nested_usage(current):
                if parent_rid in visited:
                    continue
                visited.add(parent_rid)
                try:
                    parent = self._store.get(parent_rid)
                except KeyError:
                    continue
                if self._is_public_builtin(parent_rid):
                    result.append(parent)
                q.append(parent_rid)
        return result

    def update_builtin_with_cascade(
        self,
        rid: str,
        *,
        update: BuiltinUpdateRequest,
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
        descriptor = self.get_descriptor(rid)
        if descriptor is None:
            raise ValueError("Resource is not a built-in resource")

        config = update.config
        name = update.name
        available_to_all = update.available_to_all

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

        ends_public = available_to_all is True or (
            available_to_all is None and descriptor.visibility == ResourceVisibility.PUBLIC
        )
        if available_to_all is False and descriptor.visibility == ResourceVisibility.PUBLIC:
            self._ensure_no_public_dependents(resource)

        # Persist config/name changes first — cascade validation below reads dependencies
        # via fresh store lookups, so it must see any newly-added refs. Force DRAFT during
        # this intermediate save so a rejected cascade never leaves this resource public
        # while referencing an invisible dependency.
        updated = self._store.update(resource)
        self._set_visibility(rid, ResourceVisibility.DRAFT)

        cascaded: List[Resource] = []
        if ends_public:
            cascaded = self._cascade_promote_dependencies(rid)
            self._set_visibility(rid, ResourceVisibility.PUBLIC)
        return updated, cascaded

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
