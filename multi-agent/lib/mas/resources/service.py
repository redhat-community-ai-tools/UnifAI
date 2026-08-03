import logging
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from global_utils.utils.crypto import FieldCipher
from mas.core.identity import Identity
from mas.resources.registry import ResourcesRegistry
from mas.catalog.element_registry import ElementRegistry
from mas.resources.models import Resource, ResourceQuery
from mas.resources.builtin_models import BuiltinUpdateRequest, identity_to_key
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.core.enums import ResourceCategory, ResourceOwnership, ResourceVisibility
from mas.core.ref import RefWalker
from mas.core.dto import GroupedCount
from mas.core.element_meta import ElementConfigMeta
from mas.elements.common.validator import ElementValidationResult, ValidationContext
from mas.elements.common.card import ElementCard
from mas.catalog.card_service import ElementCardService
from mas.resources.resolver import DependencyResolver
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.builtin_service import BuiltinResourceService
from mas.resources.ports import CredentialCleanupPort
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
)
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)

class ResourcesService:
    """
    Public facade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
            validation_service: Optional[ElementValidationService] = None,
            card_service: Optional[ElementCardService] = None,
            auth_service: Optional[CredentialCleanupPort] = None,
            encryption_key: str = "",
    ):
        self._store = resource_registry
        self.element_registry = element_registry
        self._builtin_user_config_repo = builtin_user_config_repo
        self._card_service = card_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)
        self._validation_service = validation_service
        self._auth_service = auth_service
        self._cipher = FieldCipher(encryption_key) if encryption_key else None
        self._fields = ResourceFieldEncryption(element_registry, self._cipher)
        # Built-in admin lifecycle + per-identity overlays live in their own
        # collaborator (see module docstring there); ResourcesService remains
        # the sole public facade and delegates to it below.
        self.builtin = BuiltinResourceService(
            resource_registry=resource_registry,
            element_registry=element_registry,
            field_encryption=self._fields,
            builtin_user_config_repo=builtin_user_config_repo,
        )

    # ---------- CRUD ----------
    def create(self, *, identity: Identity, category, type, name, config) -> Resource:
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
        )
        return self._store.create(doc)

    def save_resource(self, resource: Resource) -> Resource:
        """
        Save a pre-built Resource directly.

        Use this when you already have a validated Resource object.
        Skips schema validation since the Resource is already built.
        """
        return self._store.create(resource)

    def update(self, rid: str, *, config: dict, name: str = None) -> Resource:
        doc = self._store.get(rid)
        old_server_id = doc.cfg_dict.get("server_identifier", "")

        model_cls = self.element_registry.get_schema(
            ResourceCategory(doc.category), doc.type)
        cfg_model = model_cls(**config)

        nested_refs = list(RefWalker.external_rids(cfg_model))

        doc.cfg_dict = self._fields.encrypt_fields(
            cfg_model.model_dump(mode="json"), model_cls,
            category=doc.category, type_key=doc.type,
        )
        doc.nested_refs = nested_refs

        if name is not None:
            doc.name = name

        result = self._store.update(doc)

        new_server_id = doc.cfg_dict.get("server_identifier", "")
        if old_server_id and old_server_id != new_server_id:
            self._cleanup_orphaned_credential(doc.identity, old_server_id)

        return result

    def delete(self, rid: str) -> None:
        doc = self._store.get(rid)
        self._store.delete(rid)
        if (
            doc.ownership == ResourceOwnership.BUILTIN
            and self._builtin_user_config_repo
        ):
            self._builtin_user_config_repo.delete_all_for_resource(rid)
        server_id = doc.cfg_dict.get("server_identifier", "")
        if server_id:
            self._cleanup_orphaned_credential(doc.identity, server_id)

    # ---------- READ ----------
    def get(self, rid: str) -> Resource:
        """Get a single resource by ID."""
        return self._store.get(rid)

    def get_visible(
        self, rid: str, *, identity: Optional[Identity] = None, is_admin: bool = False,
    ) -> Resource:
        """Get a resource by ID, enforcing draft-builtin visibility and ownership.

        Draft built-ins are only visible to admins. Non-admin callers
        receive a KeyError (404) for draft built-ins.

        When ``identity`` is provided, a custom resource owned by a
        different identity is likewise hidden (KeyError) from non-admin
        callers — otherwise any authenticated caller could read another
        user's or team's private resource just by guessing/enumerating its
        rid. ``identity`` is optional (defaults to no ownership check) since
        several internal callers (dependency resolution, card building,
        blueprint validation) intentionally look up resources without
        scoping to a single identity.
        """
        resource = self._store.get(rid)
        if is_admin:
            return resource
        if (
            resource.ownership == ResourceOwnership.BUILTIN
            and resource.visibility != ResourceVisibility.PUBLIC
        ):
            raise KeyError(rid)
        if (
            identity is not None
            and resource.ownership != ResourceOwnership.BUILTIN
            and (
                resource.identity.type != identity.type
                or resource.identity.id != identity.id
            )
        ):
            raise KeyError(rid)
        return resource

    def find_resources(self, identity: Identity, category: Optional[str] = None,
                       type: Optional[str] = None, ownership: Optional[str] = None,
                       limit: int = 50, offset: int = 0,
                       is_admin: bool = False) -> Tuple[List[dict], int]:
        """Find resources with optional filtering and pagination.

        Returns serialized resource dicts. Built-ins include a
        ``user_configured`` flag indicating whether the caller has an overlay.
        Draft built-ins are only included when ``ownership=builtin`` is
        requested by an admin caller.
        """
        category_enum = ResourceCategory(category) if category else None
        ownership_enum = ResourceOwnership(ownership) if ownership else None

        query = ResourceQuery(
            identity=identity,
            category=category_enum,
            type=type,
            ownership=ownership_enum,
            limit=limit,
            offset=offset,
            is_admin=is_admin,
        )
        resources, total = self._store.find_resources(query)
        return self._serialize_with_user_configured(resources, identity), total

    # ---------- resolve ----------
    def resolve(
        self, rid: str, identity: Optional[Identity] = None, is_admin: bool = False,
    ) -> BaseModel:
        """Resolve a resource by rid into its validated config model.

        Enforces the same draft-builtin visibility as ``get_visible`` —
        a non-admin caller cannot resolve (and thereby decrypt) a draft
        built-in's config just by knowing its rid.
        """
        resource = self.get_visible(rid, identity=identity, is_admin=is_admin)
        return self.resolve_resource(resource, identity=identity)

    def resolve_resource(self, resource: Resource, identity: Optional[Identity] = None) -> BaseModel:
        """Resolve an already-fetched ``Resource`` into its validated config model.

        Same behavior as ``resolve(rid, identity)`` but skips the redundant
        ``_store.get()`` lookup when the caller already has the ``Resource``
        in hand (e.g. blueprint resolution, which needs the resource itself
        for category/type/name before resolving its config).
        """
        # raw_config_for() decrypts ENCRYPTED_FIELDS values so downstream
        # elements (e.g. sandboxes, MCP clients) receive plaintext secrets
        # rather than ciphertext.
        config = self._store.raw_config_for(resource)

        if resource.ownership == ResourceOwnership.BUILTIN and identity:
            # A caller-supplied credential (below) must always win over the
            # resource's shared base value for per-user secret fields — see
            # `strip_unconfigured_secrets` for why the base value can't be
            # trusted as a fallback.
            config = self.builtin.strip_unconfigured_secrets(resource, config)
            overlay = self.builtin.resolve_overlay(resource, identity)
            if overlay:
                config.update(overlay)

        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type)
        return model_cls(**config)

    def get_dict(self, rid: str) -> dict:
        """Raw JSON for UI."""
        return self._store.raw_config(rid)

    def exists_by_name(
        self, identity: Identity, category: str, type_: str, name: str,
    ) -> bool:
        """Whether a resource with *name* already exists for *identity* (name-conflict check)."""
        return self._store.exists_by_name(identity, category, type_, name)

    @staticmethod
    def get_resource_schema() -> dict:
        """Get the JSON schema for Resource model."""
        return Resource.model_json_schema()

    # ---------- Statistics ----------
    def count(self, identity: Identity, filter: Dict[str, Any] = None) -> int:
        return self._store.count(identity, filter)

    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None,
    ) -> List[GroupedCount]:
        """
        Group resources by specified fields and return counts.
        Performs efficient server-side grouping via the registry.
        """
        return self._store.group_count(identity, group_by, filter)

    # ---------- Validation ----------
    def validate_resource(
        self,
        rid: str,
        identity: Optional[Identity] = None,
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
        is_admin: bool = False,
    ) -> ElementValidationResult:
        """
        Validate a saved resource and all its transitive dependencies.

        When ``identity`` is provided, built-in overlay configs are merged
        into the validation context so user-specific settings participate.
        Draft built-ins are only visible to admins — non-admin callers get
        a ``KeyError`` (404) rather than being able to probe draft resources
        through the validation endpoint.
        """
        self._ensure_validation_service()

        self.get_visible(rid, identity=identity, is_admin=is_admin)

        ordered_rids = self._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")

        ordered_configs = self._build_configs_from_rids(
            ordered_rids, identity=identity, is_admin=is_admin,
        )

        return self._validate_and_get(
            ordered_configs, rid, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_resources(
        self,
        rids: List[str],
        identity: Optional[Identity] = None,
        user_id: str = "",
        timeout_seconds: float = 10.0,
        max_workers: int = 10,
        credential_user_id: str = "",
        is_admin: bool = False,
    ) -> List[ElementValidationResult]:
        """
        Validate multiple resources in parallel.

        Uses a thread pool for concurrent validation while preserving
        the order of results to match the input order.
        """
        self._ensure_validation_service()

        if not rids:
            return []

        if len(rids) == 1:
            return [
                self._validate_resource_safe(
                    rids[0], identity, user_id, timeout_seconds, credential_user_id, is_admin,
                ),
            ]

        return self._validate_in_parallel(
            rids, identity, user_id, timeout_seconds, max_workers, credential_user_id, is_admin,
        )

    def _validate_in_parallel(
        self,
        rids: List[str],
        identity: Optional[Identity],
        user_id: str,
        timeout_seconds: float,
        max_workers: int,
        credential_user_id: str = "",
        is_admin: bool = False,
    ) -> List[ElementValidationResult]:
        """Execute validations concurrently with order preservation."""
        results: List[Optional[ElementValidationResult]] = [None] * len(rids)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    self._validate_resource_safe,
                    rid, identity, user_id, timeout_seconds, credential_user_id, is_admin,
                ): idx
                for idx, rid in enumerate(rids)
            }

            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()

        return results

    def _validate_resource_safe(
        self,
        rid: str,
        identity: Optional[Identity] = None,
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
        is_admin: bool = False,
    ) -> ElementValidationResult:
        """Validate a single resource with exception handling."""
        try:
            return self.validate_resource(
                rid=rid,
                identity=identity,
                user_id=user_id,
                timeout_seconds=timeout_seconds,
                credential_user_id=credential_user_id,
                is_admin=is_admin,
            )
        except KeyError:
            return ElementValidationResult.create_error(
                rid=rid,
                error=f"Resource not found: {rid}"
            )
        except Exception as e:
            return ElementValidationResult.create_error(
                rid=rid,
                error=f"Validation failed: {str(e)}"
            )

    def validate_config(
        self,
        category: str,
        element_type: str,
        config: dict,
        name: Optional[str] = None,
        timeout_seconds: float = 10.0,
    ) -> ElementValidationResult:
        """
        Validate an inline config before saving.

        This validates a resource config without requiring it to be saved first.
        Useful for UI validation before creating a resource.
        """
        self._ensure_validation_service()

        category_enum = ResourceCategory(category)
        model_cls = self.element_registry.get_schema(category_enum, element_type)
        cfg_model = model_cls(**config)

        nested_refs = list(RefWalker.external_rids(cfg_model))
        dep_rids = self._resolve_transitive_deps(nested_refs)

        ordered_configs = self._build_configs_from_rids(dep_rids)

        ordered_configs.append(ElementConfigMeta(
            rid="inline",
            category=category_enum,
            type_key=element_type,
            name=name or "inline",
            config=cfg_model,
            dependency_rids=nested_refs,
        ))

        return self._validate_and_get(ordered_configs, "inline", timeout_seconds)

    # ---------- Card Building ----------
    def get_cards(
        self,
        rids: List[str],
        identity: Optional[Identity] = None,
        is_admin: bool = False,
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a list of resources and their dependencies.

        Enforces draft-builtin visibility on each requested rid (raises
        ``KeyError`` for a non-admin caller requesting a draft built-in).
        Resolves all transitive dependencies and builds cards for all
        elements in dependency order. When ``identity`` is provided, each
        built-in dependency's card reflects the caller's configured overlay
        rather than always showing the resource's raw defaults.
        """
        self._ensure_card_service()

        for rid in rids:
            self.get_visible(rid, identity=identity, is_admin=is_admin)

        all_rids = self._dependency_resolver.resolve_all_with_deps(rids)
        configs = self._build_configs_from_rids(all_rids, identity=identity, is_admin=is_admin)

        return self._card_service.build_all_cards(configs)

    def get_card(
        self,
        rid: str,
        identity: Optional[Identity] = None,
        is_admin: bool = False,
    ) -> ElementCard:
        """
        Get element card for a single resource.

        Resolves all transitive dependencies and builds cards,
        returning only the card for the requested resource.
        """
        cards = self.get_cards([rid], identity=identity, is_admin=is_admin)
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

    # ---------- Built-in Resource Operations ----------
    #
    # Thin delegates onto ``BuiltinResourceService`` (``self.builtin``), which
    # owns the actual admin CRUD / overlay lifecycle. Kept here so external
    # callers (Flask endpoints, tests) continue to go through the single
    # ``ResourcesService`` facade per the "Service as Public API" pattern —
    # only the internal implementation is split out.

    def find_all_builtins(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
    ) -> List[Resource]:
        """Return all built-in resources (public and draft), for admin listing."""
        return self.builtin.find_all_builtins(category=category, type=type)

    def get_builtin_schema(self, rid: str, *, is_admin: bool = False) -> dict:
        """Return the element JSON schema with readOnly annotations for a built-in resource."""
        return self.builtin.get_builtin_schema(rid, is_admin=is_admin)

    def get_user_config(
        self,
        rid: str,
        identity: Identity,
    ) -> Dict[str, Any] | None:
        """Return the user's current overlay for a built-in resource, or None."""
        return self.builtin.get_user_config(rid, identity)

    def configure_builtin(
        self,
        rid: str,
        identity: Identity,
        config: Dict[str, Any],
    ) -> Resource:
        """Save per-user/team configuration for a built-in resource."""
        return self.builtin.configure_builtin(rid, identity, config)

    def create_builtin_with_cascade(
        self,
        *,
        identity: Identity,
        category: str,
        type: str,
        name: str,
        config: dict,
        available_to_all: bool = False,
    ) -> Tuple[Resource, List[Resource]]:
        """Create a resource directly as built-in (admin only).

        Returns ``(resource, cascaded)`` — ``cascaded`` lists any aggregated
        elements (LLMs, providers, tools, etc.) that were newly promoted to
        public alongside it, for the caller to surface a disclaimer.
        """
        return self.builtin.create_builtin_with_cascade(
            identity=identity, category=category, type=type, name=name,
            config=config, available_to_all=available_to_all,
        )

    def promote_with_cascade(self, rid: str) -> Tuple[Resource, List[Resource]]:
        """Make a resource a public built-in (admin only).

        Returns ``(resource, cascaded)`` — ``cascaded`` lists any aggregated
        elements newly promoted to public alongside it.
        """
        return self.builtin.promote_with_cascade(rid)

    def demote(self, rid: str) -> Resource:
        """Demote a public built-in to draft (admin-only visibility)."""
        return self.builtin.demote(rid)

    def update_builtin_with_cascade(
        self,
        rid: str,
        *,
        config: Optional[dict] = None,
        name: Optional[str] = None,
        available_to_all: Optional[bool] = None,
    ) -> Tuple[Resource, List[Resource]]:
        """Update a built-in resource (admin only).

        Returns ``(resource, cascaded)`` — ``cascaded`` lists any aggregated
        elements newly promoted to public alongside it.
        """
        update = BuiltinUpdateRequest(
            config=config, name=name, available_to_all=available_to_all,
        )
        return self.builtin.update_builtin_with_cascade(rid, update=update)

    def toggle_visibility_with_cascade(
        self, rid: str, *, available_to_all: bool,
    ) -> Tuple[Resource, List[Resource]]:
        """Set visibility of a built-in resource (admin only).

        Returns ``(resource, cascaded)`` — ``cascaded`` lists any aggregated
        elements newly promoted to public alongside it (empty when demoting).
        """
        return self.builtin.toggle_visibility_with_cascade(rid, available_to_all=available_to_all)

    def preview_cascade_targets(self, rid: str) -> List[Resource]:
        """Resources that would be newly promoted if *rid* were promoted.

        Read-only preview — does not mutate anything.
        """
        return self.builtin.preview_cascade_targets(rid)

    def guard_write_access(
        self, rid: str, identity: Identity, is_admin: bool,
    ) -> Resource:
        """Authorize a mutation (update/delete) on a resource.

        Raises:
            BuiltInWriteProtectedError: resource is built-in and caller is not admin.
            ResourceAccessDeniedError: resource is a custom resource owned by a
                different identity (user or team) and caller is not admin.

        Admins bypass both checks. Returns the resource so callers that need
        it (e.g. ``update``) can avoid a second lookup.
        """
        resource = self._store.get(rid)
        if is_admin:
            return resource
        if resource.ownership == ResourceOwnership.BUILTIN:
            raise BuiltInWriteProtectedError()
        if (
            resource.identity.type != identity.type
            or resource.identity.id != identity.id
        ):
            raise ResourceAccessDeniedError(rid)
        return resource

    # ---------- Internal Helpers ----------

    def _cleanup_orphaned_credential(self, identity: Identity, server_id: str) -> None:
        """Delete the stored credential if no other resource uses the same server_identifier."""
        if not self._auth_service:
            return
        remaining = self._store.count_by_config_field(
            identity, "server_identifier", server_id,
        )
        if remaining == 0:
            self._auth_service.delete_credential(identity.id, server_id)

    # ---------- Helpers ----------
    def _serialize_with_user_configured(
        self,
        resources: List[Resource],
        identity: Identity,
    ) -> List[dict]:
        """Serialize resources and attach ``user_configured`` for built-ins."""
        configured_rids: set = set()
        if self._builtin_user_config_repo:
            key = identity_to_key(identity)
            for cfg in self._builtin_user_config_repo.find_by_identity(key):
                configured_rids.add(cfg.resource_id)

        result = []
        for doc in resources:
            data = doc.model_dump(mode="json")
            if doc.ownership == ResourceOwnership.BUILTIN:
                data["user_configured"] = doc.rid in configured_rids
            result.append(data)
        return result

    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if not self._validation_service:
            raise RuntimeError("ValidationService not configured")

    def _ensure_card_service(self) -> None:
        """Raise if card service not configured."""
        if not self._card_service:
            raise RuntimeError("CardService not configured")

    def _build_configs_from_rids(
        self, rids: List[str], identity: Optional[Identity] = None, is_admin: bool = False,
    ) -> List[ElementConfigMeta]:
        """Build ElementConfigMeta list from saved resource rids.

        Enforces draft-builtin visibility on every rid — including
        transitive dependencies, not just the originally requested one —
        via ``get_visible`` so a non-admin caller can't reach a draft
        built-in's (decrypted) config through a dependency chain.

        For a built-in resource, also checks whether the resolved config is
        still missing a required per-identity secret (e.g. an MCP bearer
        token nobody configured for this caller) — see
        ``BuiltinResourceService.find_missing_required_overlay_fields``.
        For a custom resource, the equivalent check is scoped to the schema
        itself rather than an overlay — see
        ``ResourceFieldEncryption.find_missing_conditionally_required_secrets``
        — since the caller's own resource simply has the field left empty
        (e.g. they picked "access token" auth but never filled in a bearer
        token). Either way, the config is flagged with
        ``validation_override_error`` so validation fails deterministically
        instead of letting the element's validator probe a connection it
        was never meant to make (which could accidentally "succeed"
        against a server that happens to tolerate unauthenticated
        requests).
        """
        configs: List[ElementConfigMeta] = []
        for rid in rids:
            resource = self.get_visible(rid, identity=identity, is_admin=is_admin)
            config = self.resolve_resource(resource, identity=identity)

            override_error = None
            if resource.ownership == ResourceOwnership.BUILTIN and identity:
                missing = self.builtin.find_missing_required_overlay_fields(resource, config)
                if missing:
                    override_error = (
                        f"Requires your own {', '.join(missing)} — configure it for "
                        f"'{resource.name}' in your inventory before it can be validated."
                    )
            elif resource.ownership != ResourceOwnership.BUILTIN:
                missing = self._fields.find_missing_conditionally_required_secrets(
                    resource.category, resource.type, config
                )
                if missing:
                    override_error = (
                        f"{', '.join(missing)} is required for '{resource.name}' — "
                        f"set it in the resource's configuration before it can be validated."
                    )

            configs.append(ElementConfigMeta(
                rid=rid,
                category=resource.category,
                type_key=resource.type,
                name=resource.name,
                config=config,
                dependency_rids=list(resource.nested_refs),
                validation_override_error=override_error,
            ))
        return configs

    def _resolve_transitive_deps(self, ref_rids: List[str]) -> List[str]:
        """Resolve refs to ordered list of all transitive dependency rids."""
        return self._dependency_resolver.resolve_all_with_deps(ref_rids)

    def _validate_and_get(
        self,
        ordered_configs: List[ElementConfigMeta],
        target_rid: str,
        timeout_seconds: float,
        user_id: str = "",
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """Validate configs in order and return result for target rid."""
        context = ValidationContext(
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            credential_user_id=credential_user_id,
            auth_service=self._auth_service,
        )
        results = self._validation_service.validate_ordered(ordered_configs, context)
        return results[target_rid]

