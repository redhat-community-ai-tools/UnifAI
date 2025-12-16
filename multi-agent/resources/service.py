from typing import List, Optional, Tuple, Dict, Any
from .registry import ResourcesRegistry
from catalog.element_registry import ElementRegistry
from .models import ResourceDoc, ResourceQuery
from core.enums import ResourceCategory
from core.ref import RefWalker
from core.dto import GroupedCount
from pydantic import BaseModel


class ResourcesService:
    """
    Public façade. Performs schema validation via ElementRegistry
    and delegates storage to ResourcesRegistry.
    """

    def __init__(
            self,
            resource_registry: ResourcesRegistry,
            element_registry: ElementRegistry,
    ):
        self._store = resource_registry
        self.element_registry = element_registry

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
