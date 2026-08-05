import logging
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from mas.resources.registry import ResourcesRegistry
from mas.catalog.element_registry import ElementRegistry
from mas.resources.models import Resource
from mas.resources.builtin_models import identity_to_key
from mas.resources.repository.builtin_user_config_repository import BuiltinUserConfigRepository
from mas.core.enums import ResourceCategory
from mas.core.ref import RefWalker
from mas.core.dto import GroupedCount
from mas.core.element_meta import ElementConfigMeta
from mas.elements.common.validator import ElementValidationResult, ValidationContext
from mas.elements.common.card import ElementCard
from mas.catalog.card_service import ElementCardService
from mas.resources.resolver import DependencyResolver
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.builtin_service import BuiltinResourceService
from mas.resources.ports import CredentialCleanupPort, AdminEditLockReader
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceLockedError,
)
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)

class ResourcesService:
    """
    Public facade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.

    Built-in-awareness (is this resource a built-in? what's its
    visibility? what's the caller's config overlay?) is never decided
    here directly — it's delegated through the small helper methods on
    the injected ``BuiltinResourceService`` (``self._builtin``), which is
    the sole owner of the ``ResourceOwnership``/``ResourceVisibility``
    concepts. This class carries zero knowledge of those enums; see
    ``resources.md`` for the full rationale.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            builtin_service: BuiltinResourceService,
            field_encryption: ResourceFieldEncryption,
            builtin_user_config_repo: Optional[BuiltinUserConfigRepository] = None,
            validation_service: Optional[ElementValidationService] = None,
            card_service: Optional[ElementCardService] = None,
            auth_service: Optional[CredentialCleanupPort] = None,
            admin_lock_reader: Optional[AdminEditLockReader] = None,
    ):
        self._store = resource_registry
        self.element_registry = element_registry
        self._builtin_user_config_repo = builtin_user_config_repo
        self._card_service = card_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)
        self._validation_service = validation_service
        self._auth_service = auth_service
        self._fields = field_encryption
        self._admin_lock_reader = admin_lock_reader
        # Built-in admin lifecycle + per-identity overlays live in their own
        # peer service, injected by the container so it's shared with
        # ``builtins.py``/``ShareCloner`` rather than constructed here.
        # Internal attribute (not part of the public surface) — external
        # callers needing the built-in admin/overlay API go through
        # ``container.builtin_resource_service`` directly.
        self._builtin = builtin_service

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
        self._builtin.cleanup_on_delete(rid)
        server_id = doc.cfg_dict.get("server_identifier", "")
        if server_id:
            self._cleanup_orphaned_credential(doc.identity, server_id)

    # ---------- READ ----------
    def get(self, rid: str) -> Resource:
        """Get a single resource by ID."""
        return self._store.get(rid)

    def get_visible(
        self, rid: str, *, caller: CallerScope = CallerScope(),
    ) -> Resource:
        """Get a resource by ID, enforcing draft-builtin visibility and ownership.

        Draft built-ins are only visible to admins. Non-admin callers
        receive a KeyError (404) for draft built-ins.

        When ``caller.identity`` is set, a custom resource owned by a
        different identity is likewise hidden (KeyError) from non-admin
        callers — otherwise any authenticated caller could read another
        user's or team's private resource just by guessing/enumerating its
        rid. ``caller.identity`` may be ``None`` (defaults to no ownership
        check) since several internal callers (dependency resolution, card
        building, blueprint validation) intentionally look up resources
        without scoping to a single identity.
        """
        resource = self._store.get(rid)
        if caller.is_admin:
            return resource
        if not self._builtin.is_visible_to(rid, caller.is_admin):
            raise KeyError(rid)
        if (
            caller.identity is not None
            and not self._builtin.is_builtin(rid)
            and (
                resource.identity.type != caller.identity.type
                or resource.identity.id != caller.identity.id
            )
        ):
            raise KeyError(rid)
        return resource

    def find_resources(self, category: Optional[str] = None,
                       type: Optional[str] = None, ownership: Optional[str] = None,
                       limit: int = 50, offset: int = 0,
                       caller: CallerScope = CallerScope()) -> Tuple[List[dict], int]:
        """Find resources with optional filtering and pagination, scoped to ``caller.identity``.

        Returns serialized resource dicts. Built-ins include a
        ``user_configured`` flag indicating whether the caller has an overlay.
        Draft built-ins are only included when ``ownership=builtin`` is
        requested by an admin caller (``caller.is_admin``).
        """
        category_enum = ResourceCategory(category) if category else None

        resources, total = self._builtin.find_visible(
            identity=caller.identity,
            category=category_enum.value if category_enum else None,
            type=type,
            ownership=ownership,
            is_admin=caller.is_admin,
            limit=limit,
            offset=offset,
            sort_by="created",
            sort_order="desc",
        )
        return self.to_dicts(resources, identity=caller.identity), total

    # ---------- resolve ----------
    def resolve(
        self, rid: str, caller: CallerScope = CallerScope(),
    ) -> BaseModel:
        """Resolve a resource by rid into its validated config model.

        Enforces the same draft-builtin visibility as ``get_visible`` —
        a non-admin caller cannot resolve (and thereby decrypt) a draft
        built-in's config just by knowing its rid.
        """
        resource = self.get_visible(rid, caller=caller)
        return self.resolve_resource(resource, caller=caller)

    def resolve_resource(self, resource: Resource, caller: CallerScope = CallerScope()) -> BaseModel:
        """Resolve an already-fetched ``Resource`` into its validated config model.

        Same behavior as ``resolve(rid, caller)`` but skips the redundant
        ``_store.get()`` lookup when the caller already has the ``Resource``
        in hand (e.g. blueprint resolution, which needs the resource itself
        for category/type/name before resolving its config).
        """
        # raw_config_for() decrypts ENCRYPTED_FIELDS values so downstream
        # elements (e.g. sandboxes, MCP clients) receive plaintext secrets
        # rather than ciphertext.
        config = self._store.raw_config_for(resource)
        # For a built-in, merges the caller's per-identity overlay in; a
        # no-op for a plain custom resource or an anonymous caller. See
        # `BuiltinResourceService.resolve_config`.
        config = self._builtin.resolve_config(resource, config, caller.identity)

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
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """
        Validate a saved resource and all its transitive dependencies.

        When ``caller.identity`` is set, built-in overlay configs are merged
        into the validation context so user-specific settings participate.
        Draft built-ins are only visible to admins — non-admin callers get
        a ``KeyError`` (404) rather than being able to probe draft resources
        through the validation endpoint.
        """
        self._ensure_validation_service()

        self.get_visible(rid, caller=caller)

        ordered_rids = self._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")

        ordered_configs = self._build_configs_from_rids(ordered_rids, caller=caller)

        return self._validate_and_get(
            ordered_configs, rid, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_resources(
        self,
        rids: List[str],
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        max_workers: int = 10,
        credential_user_id: str = "",
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
                    rids[0], caller, user_id, timeout_seconds, credential_user_id,
                ),
            ]

        return self._validate_in_parallel(
            rids, caller, user_id, timeout_seconds, max_workers, credential_user_id,
        )

    def _validate_in_parallel(
        self,
        rids: List[str],
        caller: CallerScope,
        user_id: str,
        timeout_seconds: float,
        max_workers: int,
        credential_user_id: str = "",
    ) -> List[ElementValidationResult]:
        """Execute validations concurrently with order preservation."""
        results: List[Optional[ElementValidationResult]] = [None] * len(rids)

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_index = {
                executor.submit(
                    self._validate_resource_safe,
                    rid, caller, user_id, timeout_seconds, credential_user_id,
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
        caller: CallerScope = CallerScope(),
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """Validate a single resource with exception handling."""
        try:
            return self.validate_resource(
                rid=rid,
                caller=caller,
                user_id=user_id,
                timeout_seconds=timeout_seconds,
                credential_user_id=credential_user_id,
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
        caller: CallerScope = CallerScope(),
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a list of resources and their dependencies.

        Enforces draft-builtin visibility on each requested rid (raises
        ``KeyError`` for a non-admin caller requesting a draft built-in).
        Resolves all transitive dependencies and builds cards for all
        elements in dependency order. When ``caller.identity`` is set, each
        built-in dependency's card reflects the caller's configured overlay
        rather than always showing the resource's raw defaults.
        """
        self._ensure_card_service()

        for rid in rids:
            self.get_visible(rid, caller=caller)

        all_rids = self._dependency_resolver.resolve_all_with_deps(rids)
        configs = self._build_configs_from_rids(all_rids, caller=caller)

        return self._card_service.build_all_cards(configs)

    def get_card(
        self,
        rid: str,
        caller: CallerScope = CallerScope(),
    ) -> ElementCard:
        """
        Get element card for a single resource.

        Resolves all transitive dependencies and builds cards,
        returning only the card for the requested resource.
        """
        cards = self.get_cards([rid], caller=caller)
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

    # ---------- Write-access guard ----------
    #
    # Generic — used by resources.py for the base resource.update/
    # resource.delete routes (admins use these to mutate built-in resources
    # too). Includes the admin edit-lock check for built-in resources so
    # the adapter layer never inspects resource ownership to decide whether
    # an additional check is needed.  The admin-only built-in lifecycle
    # (find_all_builtins, create/promote/demote/update/toggle, schema and
    # per-identity overlay access) lives entirely on the peer
    # ``BuiltinResourceService`` now — see ``container.builtin_resource_service``
    # and ``endpoints/builtins.py``, which inject/consume it directly.

    def guard_write_access(
        self, rid: str, caller: CallerScope, *, username: str = "",
    ) -> Resource:
        """Authorize a mutation (update/delete) on a resource.

        ``username`` is the authenticated individual user (e.g. ``"alice"``),
        only needed for the admin edit-lock comparison.  The adapter reads it
        from the request context and passes it here — ``CallerScope`` carries
        only the domain-level identity + access level.

        Raises:
            BuiltInWriteProtectedError: resource is built-in and caller is not admin.
            ResourceAccessDeniedError: resource is a custom resource owned by a
                different identity (user or team) and caller is not admin.
            ResourceLockedError: resource is a built-in whose admin edit lock is
                held by a different admin (409 at the HTTP layer).

        Admins bypass ownership checks but are still subject to the admin
        edit lock for built-in resources.  Returns the resource so callers
        that need it (e.g. ``update``) can avoid a second lookup.
        """
        resource = self._store.get(rid)
        is_builtin = self._builtin.is_builtin(rid)
        if caller.is_admin:
            if is_builtin:
                self._check_admin_edit_lock(rid, username)
            return resource
        if is_builtin:
            raise BuiltInWriteProtectedError()
        if (
            caller.identity is None
            or resource.identity.type != caller.identity.type
            or resource.identity.id != caller.identity.id
        ):
            raise ResourceAccessDeniedError(rid)
        return resource

    def _check_admin_edit_lock(self, rid: str, username: str) -> None:
        """Raise ``ResourceLockedError`` if another admin holds the edit lock.

        No-ops when the collaboration service (Redis) isn't configured,
        matching the cooperative lock's 501 fallback behavior.
        """
        if self._admin_lock_reader is None:
            return
        holder = self._admin_lock_reader.get_admin_edit_lock(rid)
        if holder is None:
            return
        if holder.user_id.casefold() == username.casefold():
            return
        raise ResourceLockedError(
            locked_by_user_id=holder.user_id,
            locked_by_display_name=holder.display_name,
        )

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

    # ---------- Serialization ----------
    def to_dict(self, resource: Resource) -> dict:
        """Serialize a single resource to a JSON-ready dict.

        The HTTP/JSON API contract keeps returning ``ownership``/
        ``visibility`` fields even though ``Resource`` itself no longer
        carries them (they moved to ``BuiltinResourceDescriptor``) — this
        stamps them back on from ``self._builtin.get_descriptor(...)`` so
        every caller (Flask endpoints, tests) sees an unchanged shape.
        Does not include ``user_configured`` — see ``to_dicts`` for the
        batch-computed variant used by listing endpoints.
        """
        data = resource.model_dump(mode="json")
        descriptor = self._builtin.get_descriptor(resource.rid)
        if descriptor is None:
            data["ownership"] = "custom"
        else:
            data["ownership"] = "builtin"
            data["visibility"] = descriptor.visibility.value
        return data

    def to_dicts(
        self,
        resources: List[Resource],
        *,
        identity: Optional[Identity] = None,
    ) -> List[dict]:
        """Serialize resources, additionally attaching ``user_configured``
        for built-ins when *identity* is given.

        Precomputes the set of built-ins *identity* has configured in a
        single query rather than one lookup per resource.
        """
        configured_rids: set = set()
        if identity is not None and self._builtin_user_config_repo:
            key = identity_to_key(identity)
            for cfg in self._builtin_user_config_repo.find_by_identity(key):
                configured_rids.add(cfg.resource_id)

        result = []
        for doc in resources:
            data = self.to_dict(doc)
            if data["ownership"] == "builtin":
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
        self, rids: List[str], caller: CallerScope = CallerScope(),
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
            resource = self.get_visible(rid, caller=caller)
            config = self.resolve_resource(resource, caller=caller)

            if self._builtin.is_builtin(rid):
                override_error = self._builtin.validation_override_error(
                    resource, config, caller.identity
                )
            else:
                override_error = None
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

