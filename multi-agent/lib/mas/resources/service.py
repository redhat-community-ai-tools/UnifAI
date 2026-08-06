import logging
from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from mas.resources.registry import ResourcesRegistry
from mas.catalog.element_registry import ElementRegistry
from mas.resources.models import Resource, ResourceQuery
from mas.core.enums import ResourceCategory
from mas.core.ref import RefWalker
from mas.core.dto import GroupedCount
from mas.core.element_meta import ElementConfigMeta
from mas.elements.common.validator import ElementValidationResult, ValidationContext
from mas.elements.common.card import ElementCard
from mas.catalog.card_service import ElementCardService
from mas.resources.resolver import DependencyResolver
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.ports import CredentialCleanupPort
from mas.resources.errors import ResourceAccessDeniedError
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)

class CoreResourceService:
    """Pure resource CRUD, validation, card building, and encryption.

    Has zero awareness of built-ins, overlays, visibility gating,
    or admin locks.  Does not import anything from ``builtin_models``,
    ``builtin_service``, ``ResourceOwnership``, or ``ResourceVisibility``.

    If the built-in feature is removed, this class doesn't change.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            field_encryption: ResourceFieldEncryption,
            validation_service: Optional[ElementValidationService] = None,
            card_service: Optional[ElementCardService] = None,
            auth_service: Optional[CredentialCleanupPort] = None,
    ) -> None:
        self._store = resource_registry
        self.element_registry = element_registry
        self._card_service = card_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)
        self._validation_service = validation_service
        self._auth_service = auth_service
        self._fields = field_encryption

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
        """Save a pre-built Resource directly.

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
        """Delete a resource.  No descriptor/overlay cleanup."""
        doc = self._store.get(rid)
        self._store.delete(rid)
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
        """Get a resource, enforcing identity-based ownership only.

        When ``caller.identity`` is set, a resource owned by a different
        identity is hidden (``KeyError``) from non-admin callers.
        ``caller.identity`` may be ``None`` (no ownership check) since
        several internal callers intentionally look up resources without
        scoping to a single identity.
        """
        resource = self._store.get(rid)
        if caller.is_admin:
            return resource
        if (
            caller.identity is not None
            and (
                resource.identity.type != caller.identity.type
                or resource.identity.id != caller.identity.id
            )
        ):
            raise KeyError(rid)
        return resource

    def find_resources(
        self,
        category: Optional[str] = None,
        type: Optional[str] = None,
        ownership: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        caller: CallerScope = CallerScope(),
    ) -> Tuple[List[dict], int]:
        """List the caller's own resources.  No built-in merging.

        ``ownership`` is accepted but ignored — it's a built-in concept.
        """
        if caller.identity is None:
            return [], 0

        category_enum = ResourceCategory(category) if category else None
        query = ResourceQuery(
            identity=caller.identity,
            category=category_enum,
            type=type,
            limit=limit,
            offset=offset,
        )
        resources, total = self._store.find_resources(query)
        return self.to_dicts(resources), total

    # ---------- resolve ----------
    def resolve(
        self, rid: str, caller: CallerScope = CallerScope(),
    ) -> BaseModel:
        """Resolve a resource by rid into its validated config model."""
        resource = self.get_visible(rid, caller=caller)
        return self.resolve_resource(resource, caller=caller)

    def resolve_resource(self, resource: Resource, caller: CallerScope = CallerScope()) -> BaseModel:
        """Resolve an already-fetched ``Resource`` into its validated config model.

        Decrypts config and returns the Pydantic model.  No overlay merge.
        """
        config = self._store.raw_config_for(resource)
        model_cls = self.element_registry.get_schema(
            ResourceCategory(resource.category), resource.type)
        return model_cls(**config)

    def get_dict(self, rid: str) -> dict:
        """Raw JSON for UI."""
        return self._store.raw_config(rid)

    def exists_by_name(
        self, identity: Identity, category: str, type_: str, name: str,
    ) -> bool:
        """Whether a resource with *name* already exists for *identity*."""
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
        """Group resources by specified fields and return counts."""
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
        """Validate a saved resource and all its transitive dependencies."""
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
        """Validate multiple resources in parallel."""
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
        """Validate an inline config before saving."""
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
        """Get element cards for a list of resources and their dependencies."""
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
        """Get element card for a single resource."""
        cards = self.get_cards([rid], caller=caller)
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

    # ---------- Write-access guard ----------

    def guard_write_access(
        self, rid: str, caller: CallerScope, *, username: str = "",
    ) -> Resource:
        """Identity-based ownership check only.

        No built-in protection, no admin edit lock check.

        Raises:
            ResourceAccessDeniedError: resource is owned by a different
                identity and caller is not admin.
        """
        resource = self._store.get(rid)
        if caller.is_admin:
            return resource
        if (
            caller.identity is None
            or resource.identity.type != caller.identity.type
            or resource.identity.id != caller.identity.id
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

    # ---------- Serialization ----------
    def to_dict(self, resource: Resource) -> dict:
        """Serialize a single resource to a JSON-ready dict.

        No ownership/visibility stamping — see ``BuiltinAwareResourceService``
        for the decorated version that stamps descriptor metadata.
        """
        return resource.model_dump(mode="json")

    def to_dicts(
        self,
        resources: List[Resource],
        *,
        identity: Optional[Identity] = None,
    ) -> List[dict]:
        """Serialize resources.

        ``identity`` is accepted but unused — the built-in-aware decorator
        uses it to attach ``user_configured`` flags.
        """
        return [self.to_dict(doc) for doc in resources]

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

        Checks whether the resolved config is missing a required secret —
        see ``ResourceFieldEncryption.find_missing_conditionally_required_secrets``.
        """
        configs: List[ElementConfigMeta] = []
        for rid in rids:
            resource = self.get_visible(rid, caller=caller)
            config = self.resolve_resource(resource, caller=caller)

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
