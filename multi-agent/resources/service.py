from typing import List, Optional, Tuple, Dict, Any

from pydantic import BaseModel

from resources.registry import ResourcesRegistry
from catalog.element_registry import ElementRegistry
from resources.models import ResourceDoc, ResourceQuery
from core.enums import ResourceCategory
from core.ref import RefWalker
from core.dto import GroupedCount
from elements.common.validator import ElementValidationResult, ValidationContext
from resources.validation.resolver import DependencyResolver
from validation.models import ConfigMeta
from validation.service import ElementValidationService


class ResourcesService:
    """
    Public façade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
            validation_service: ElementValidationService = None,
    ):
        self._store = resource_registry
        self.element_registry = element_registry
        self._validation_service = validation_service
        self._dependency_resolver = DependencyResolver(resource_registry=self._store)

    # ---------- CRUD ----------
    def create(self, *, user_id, category, type, name, config) -> ResourceDoc:
        # schema validation
        model_cls = self.element_registry.get_schema(ResourceCategory(category), type)
        cfg_model = model_cls(**config)  # Pydantic instance

        # traverse refs on the *model*
        nested_refs = list(RefWalker.external_rids(cfg_model))

        # build the document for storage
        doc = ResourceDoc(
            user_id=user_id,
            category=category,
            type=type,
            name=name,
            cfg_dict=cfg_model.model_dump(mode="json"),
            nested_refs=nested_refs,
        )
        return self._store.create(doc)

    def update(self, rid: str, *, config: dict, name: str = None) -> ResourceDoc:
        # 1. fetch immutable meta
        doc = self._store.get(rid)  # existing ResourceDoc
        model_cls = self.element_registry.get_schema(
            ResourceCategory(doc.category), doc.type)
        cfg_model = model_cls(**config)  # validate

        # 2. recompute nested refs
        nested_refs = list(RefWalker.external_rids(cfg_model))

        # 3. build a *new* ResourceDoc (immutability) or mutate doc
        doc.cfg_dict = cfg_model.model_dump(mode="json")
        doc.nested_refs = nested_refs
        
        # 4. update name if provided
        if name is not None:
            doc.name = name
            
        return self._store.update(doc)

    def delete(self, rid: str) -> None:
        self._store.delete(rid)

    # ---------- READ ----------
    def get(self, rid: str) -> ResourceDoc:
        """Get a single resource by ID."""
        return self._store.get(rid)

    def find_resources(self, user_id: str, category: Optional[str] = None,
                       type: Optional[str] = None, limit: int = 50,
                       offset: int = 0) -> Tuple[List[ResourceDoc], int]:
        """Find resources with optional filtering and pagination."""
        # Convert string category to enum if provided
        category_enum = ResourceCategory(category) if category else None

        query = ResourceQuery(
            user_id=user_id,
            category=category_enum,
            type=type,
            limit=limit,
            offset=offset
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
        """Get the JSON schema for ResourceDoc model."""
        return ResourceDoc.model_json_schema()

    # ---------- Statistics ----------
    def count(self, user_id: str, filter: Dict[str, Any] = None) -> int:
        """Count resources matching filter criteria for a user."""
        return self._store.count(user_id, filter)

    def group_count(
        self, 
        user_id: str, 
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group resources by specified fields and return counts.
        Performs efficient server-side grouping via the registry.
        
        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by (e.g., ["category", "type"])
            filter: Optional additional filter criteria
            
        Returns:
            List of GroupedCount DTOs with grouped field values and count.
            Example: [GroupedCount(fields={"category": "llm", "type": "openai"}, count=5), ...]
        """
        return self._store.group_count(user_id, group_by, filter)

    # ---------- Validation ----------
    def validate_resource(
        self,
        rid: str,
        timeout_seconds: float = 10.0,
    ) -> ElementValidationResult:
        """
        Validate a saved resource and all its transitive dependencies.
        
        Args:
            rid: Resource ID to validate
            timeout_seconds: Timeout for network checks
            
        Returns:
            ElementValidationResult for the requested resource
            
        Raises:
            RuntimeError: If validation service not configured
            KeyError: If resource not found
        """
        self._ensure_validation_service()
        
        # Resolve rids in dependency order
        ordered_rids = self._dependency_resolver.resolve_with_deps(rid)
        if not ordered_rids:
            raise KeyError(f"Resource not found: {rid}")

        # Build ConfigMeta for each rid
        ordered_configs = self._build_configs_from_rids(ordered_rids)
        
        # Validate and return result for requested rid
        return self._validate_and_get(ordered_configs, rid, timeout_seconds)

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
        
        If the config references saved resources ($ref:xxx), those dependencies
        will be validated first and their results made available to the validator.
        
        Args:
            category: Resource category (e.g., "llm", "provider", "node")
            element_type: Element type (e.g., "openai", "mcp_server")
            config: The config dict to validate
            name: Optional display name (used in validation result)
            timeout_seconds: Timeout for network checks
            
        Returns:
            ElementValidationResult for the inline config
            
        Raises:
            RuntimeError: If validation service not configured
            ValueError: If schema validation fails
            KeyError: If referenced resource not found
        """
        self._ensure_validation_service()
        
        # Schema validation - will raise ValueError if invalid
        category_enum = ResourceCategory(category)
        model_cls = self.element_registry.get_schema(category_enum, element_type)
        cfg_model = model_cls(**config)
        
        # Extract nested refs and resolve dependencies
        nested_refs = list(RefWalker.external_rids(cfg_model))
        dep_rids = self._resolve_transitive_deps(nested_refs)
        
        # Build ordered configs: dependencies first
        ordered_configs = self._build_configs_from_rids(dep_rids)
        
        # Add inline config last
        ordered_configs.append(ConfigMeta(
            rid="inline",
            category=category_enum,
            element_type=element_type,
            config=cfg_model,
            name=name,
            dependency_rids=nested_refs,
        ))
        
        # Validate and return result for inline config
        return self._validate_and_get(ordered_configs, "inline", timeout_seconds)

    # ---------- Validation Helpers ----------
    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if not self._validation_service:
            raise RuntimeError("ValidationService not configured")

    def _build_configs_from_rids(self, rids: List[str]) -> List[ConfigMeta]:
        """Build ConfigMeta list from saved resource rids."""
        configs: List[ConfigMeta] = []
        for rid in rids:
            resource = self._store.get(rid)
            config = self.resolve(rid)
            configs.append(ConfigMeta(
                rid=rid,
                category=resource.category,
                element_type=resource.type,
                config=config,
                name=resource.name,
                dependency_rids=list(resource.nested_refs),
            ))
        return configs

    def _resolve_transitive_deps(self, ref_rids: List[str]) -> List[str]:
        """Resolve refs to ordered list of all transitive dependency rids."""
        all_rids: List[str] = []
        for ref_rid in ref_rids:
            dep_rids = self._dependency_resolver.resolve_with_deps(ref_rid)
            for rid in dep_rids:
                if rid not in all_rids:
                    all_rids.append(rid)
        return all_rids

    def _validate_and_get(
        self,
        ordered_configs: List[ConfigMeta],
        target_rid: str,
        timeout_seconds: float,
    ) -> ElementValidationResult:
        """Validate configs in order and return result for target rid."""
        context = ValidationContext(timeout_seconds=timeout_seconds)
        results = self._validation_service.validate_ordered(ordered_configs, context)
        return results[target_rid]
