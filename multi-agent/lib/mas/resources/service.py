from typing import List, Optional, Tuple, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from pydantic import BaseModel

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
from mas.validation.service import ElementValidationService

class ResourcesService:
    """
    Public facade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            validation_service: ElementValidationService = None,
            card_service: ElementCardService = None,
            auth_service=None,
    ):
        self._store = resource_registry
        self.element_registry = element_registry
        self._card_service = card_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)
        self._validation_service = validation_service
        self._auth_service = auth_service

    def set_auth_service(self, auth_service) -> None:
        """Late-bind the auth service (created after ResourcesService in the container)."""
        self._auth_service = auth_service

    # ---------- CRUD ----------
    def create(self, *, identity: Identity, category, type, name, config) -> Resource:
        model_cls = self.element_registry.get_schema(ResourceCategory(category), type)
        cfg_model = model_cls(**config)

        self._run_pre_save_hook(cfg_model, identity.id)

        nested_refs = list(RefWalker.external_rids(cfg_model))

        doc = Resource(
            identity=identity,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_model.model_dump(mode="json"),
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

        self._run_pre_save_hook(cfg_model, doc.identity.id)

        nested_refs = list(RefWalker.external_rids(cfg_model))

        doc.cfg_dict = cfg_model.model_dump(mode="json")
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
        server_id = doc.cfg_dict.get("server_identifier", "")
        if server_id:
            self._cleanup_orphaned_credential(doc.identity, server_id)

    # ---------- READ ----------
    def get(self, rid: str) -> Resource:
        """Get a single resource by ID."""
        return self._store.get(rid)

    def find_resources(self, identity: Identity, category: Optional[str] = None,
                       type: Optional[str] = None, limit: int = 50,
                       offset: int = 0) -> Tuple[List[Resource], int]:
        """Find resources with optional filtering and pagination."""
        category_enum = ResourceCategory(category) if category else None

        query = ResourceQuery(
            identity=identity,
            category=category_enum,
            type=type,
            limit=limit,
            offset=offset,
        )
        return self._store.find_resources(query)

    # ---------- resolve ----------
    def resolve(self, rid: str) -> BaseModel:
        category, _type = self._store.meta(rid)
        model_cls = self.element_registry.get_schema(ResourceCategory(category), _type)
        return model_cls(**self._store.raw_config(rid))

    def get_dict(self, rid: str) -> dict:
        """Raw JSON for UI."""
        return self._store.raw_config(rid)

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
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """
        Validate a saved resource and all its transitive dependencies.
        """
        self._ensure_validation_service()

        ordered_rids = self._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")

        ordered_configs = self._build_configs_from_rids(ordered_rids)

        return self._validate_and_get(
            ordered_configs, rid, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_resources(
        self,
        rids: List[str],
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
                    rids[0], user_id, timeout_seconds, credential_user_id,
                ),
            ]

        return self._validate_in_parallel(
            rids, user_id, timeout_seconds, max_workers, credential_user_id,
        )

    def _validate_in_parallel(
        self,
        rids: List[str],
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
                    rid, user_id, timeout_seconds, credential_user_id,
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
        user_id: str,
        timeout_seconds: float,
        credential_user_id: str = "",
    ) -> ElementValidationResult:
        """Validate a single resource with exception handling."""
        try:
            return self.validate_resource(
                rid=rid,
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
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a list of resources and their dependencies.

        Resolves all transitive dependencies and builds cards for all elements
        in dependency order.
        """
        self._ensure_card_service()

        all_rids = self._dependency_resolver.resolve_all_with_deps(rids)
        configs = self._build_configs_from_rids(all_rids)

        return self._card_service.build_all_cards(configs)

    def get_card(
        self,
        rid: str,
    ) -> ElementCard:
        """
        Get element card for a single resource.

        Resolves all transitive dependencies and builds cards,
        returning only the card for the requested resource.
        """
        cards = self.get_cards([rid])
        if rid not in cards:
            raise KeyError(f"Resource not found: {rid}")
        return cards[rid]

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
    def _run_pre_save_hook(self, cfg_model: BaseModel, user_id: str) -> None:
        """Call on_pre_save on the config model if it supports it."""
        if hasattr(cfg_model, "on_pre_save"):
            cfg_model.on_pre_save(user_id, auth_service=self._auth_service)

    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if not self._validation_service:
            raise RuntimeError("ValidationService not configured")

    def _ensure_card_service(self) -> None:
        """Raise if card service not configured."""
        if not self._card_service:
            raise RuntimeError("CardService not configured")

    def _build_configs_from_rids(self, rids: List[str]) -> List[ElementConfigMeta]:
        """Build ElementConfigMeta list from saved resource rids."""
        configs: List[ElementConfigMeta] = []
        for rid in rids:
            resource = self._store.get(rid)
            config = self.resolve(rid)
            configs.append(ElementConfigMeta(
                rid=rid,
                category=resource.category,
                type_key=resource.type,
                name=resource.name,
                config=config,
                dependency_rids=list(resource.nested_refs),
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
