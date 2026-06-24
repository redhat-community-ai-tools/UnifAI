"""
Placeholder analyzer for extracting fields from element config schemas.

Creates a real Pydantic model by extracting exact field definitions
from original configs based on placeholder metadata.

SOLID Principles:
- SRP: Each method has one responsibility
- OCP: Extensible via ElementRegistry without modification
- DIP: Depends on ElementRegistry abstraction
"""
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Type, Iterator

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

from mas.catalog.element_registry import ElementRegistry
from mas.core.enums import ResourceCategory
from mas.templates.models.template import Template, PlaceholderPointer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FieldDefinition:
    """Extracted field definition for model creation."""
    name: str
    annotation: Any
    field_info: FieldInfo


class PlaceholderAnalyzer:
    """
    Analyzes templates and creates input Pydantic models.
    
    Extracts exact (annotation, FieldInfo) from original config schemas
    and builds a nested Pydantic model for user input validation.
    """
    
    # Model naming pattern
    INPUT_SUFFIX = "Input"

    def __init__(self, element_registry: ElementRegistry):
        self._registry = element_registry

    # ─────────────────────────────────────────────────────────────────────
    #  Public API
    # ─────────────────────────────────────────────────────────────────────
    def create_input_model(self, template: Template) -> Type[BaseModel]:
        """
        Create a Pydantic model for template input validation.
        
        Structure: Root → Category → Resource → Fields
        """
        category_models = self._build_all_category_models(template)
        
        if not category_models:
            return self._create_empty_model(template.name)
        
        return self._build_root_model(template.name, category_models)

    def get_json_schema(self, template: Template) -> Dict[str, Any]:
        """Get JSON Schema for template input (for UI form generation)."""
        return self.create_input_model(template).model_json_schema()

    # ─────────────────────────────────────────────────────────────────────
    #  Model Building
    # ─────────────────────────────────────────────────────────────────────
    def _build_all_category_models(
        self, 
        template: Template,
    ) -> Dict[str, Type[BaseModel]]:
        """Build models for all categories with placeholders."""
        category_models: Dict[str, Type[BaseModel]] = {}
        
        for cat_placeholder in template.placeholders.categories:
            category_model = self._build_category_model(
                template=template,
                category=cat_placeholder.category,
                resources=cat_placeholder.resources,
            )
            if category_model:
                category_models[cat_placeholder.category.value] = category_model
        
        return category_models

    def _build_category_model(
        self,
        template: Template,
        category: ResourceCategory,
        resources: List,
    ) -> Optional[Type[BaseModel]]:
        """Build model for a single category."""
        resource_models: Dict[str, Type[BaseModel]] = {}
        
        for res_placeholder in resources:
            resource_model = self._build_resource_model(
                template=template,
                category=category,
                rid=res_placeholder.rid,
                placeholders=res_placeholder.placeholders,
            )
            if resource_model:
                resource_models[res_placeholder.rid] = resource_model
        
        if not resource_models:
            return None
        
        fields = {
            rid: (model, Field(..., description=f"Input for {rid}"))
            for rid, model in resource_models.items()
        }
        
        return create_model(
            self._model_name(category.value.title()),
            **fields,
        )

    def _build_resource_model(
        self,
        template: Template,
        category: ResourceCategory,
        rid: str,
        placeholders: List[PlaceholderPointer],
    ) -> Optional[Type[BaseModel]]:
        """Build model for a single resource's placeholder fields."""
        # Find resource in draft
        resource = self._find_resource(template.draft, category, rid)
        if resource is None:
            logger.warning("Resource not found: %s/%s", category.value, rid)
            return None
        
        # Get original config schema
        schema_cls = self._get_config_schema(category, resource.type)
        if schema_cls is None:
            logger.warning("Schema not found: %s/%s", category.value, resource.type)
            return None
        
        # Extract field definitions
        field_defs = list(self._extract_fields(schema_cls, placeholders))
        if not field_defs:
            return None
        
        # Build model
        fields = {
            fd.name: (fd.annotation, fd.field_info)
            for fd in field_defs
        }
        
        return create_model(self._model_name(rid), **fields)

    def _build_root_model(
        self,
        template_name: str,
        category_models: Dict[str, Type[BaseModel]],
    ) -> Type[BaseModel]:
        """Build root model from category models."""
        fields = {
            cat_name: (model, Field(..., description=f"Input for {cat_name}"))
            for cat_name, model in category_models.items()
        }
        return create_model(self._model_name(template_name), **fields)

    def _create_empty_model(self, name: str) -> Type[BaseModel]:
        """Create empty model when no placeholders exist."""
        return create_model(self._model_name(name))

    # ─────────────────────────────────────────────────────────────────────
    #  Field Extraction
    # ─────────────────────────────────────────────────────────────────────
    def _extract_fields(
        self,
        schema_cls: Type[BaseModel],
        placeholders: List[PlaceholderPointer],
    ) -> Iterator[FieldDefinition]:
        """Extract field definitions from schema based on placeholders."""
        for placeholder in placeholders:
            field_def = self._extract_single_field(schema_cls, placeholder)
            if field_def:
                yield field_def

    def _extract_single_field(
        self,
        schema_cls: Type[BaseModel],
        placeholder: PlaceholderPointer,
    ) -> Optional[FieldDefinition]:
        """Extract a single field definition."""
        # Get field name (last segment of path)
        field_name = placeholder.field_path.split(".")[-1]
        
        if field_name not in schema_cls.model_fields:
            logger.warning("Field '%s' not found in %s", field_name, schema_cls.__name__)
            return None
        
        original = schema_cls.model_fields[field_name]
        field_info = self._create_field_info(original, placeholder)
        
        return FieldDefinition(
            name=field_name,
            annotation=original.annotation,
            field_info=field_info,
        )

    def _create_field_info(
        self,
        original: FieldInfo,
        placeholder: PlaceholderPointer,
    ) -> FieldInfo:
        """Create FieldInfo with placeholder overrides for title/description."""
        is_required = placeholder.required
        
        # Determine default value
        if is_required:
            default = ...
        elif original.default is PydanticUndefined:
            default = None
        else:
            default = original.default
        
        return Field(
            default=default,
            title=placeholder.label or original.title,
            description=placeholder.hint or original.description,
            json_schema_extra=original.json_schema_extra,
        )

    # ─────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────
    def _find_resource(
        self,
        draft,
        category: ResourceCategory,
        rid: str,
    ):
        """Find resource in draft by category and rid."""
        resources = getattr(draft, category.value, [])
        for resource in resources:
            if resource.rid.ref == rid:
                return resource
        return None

    def _get_config_schema(
        self,
        category: ResourceCategory,
        element_type: str,
    ) -> Optional[Type[BaseModel]]:
        """Get config schema from registry."""
        try:
            return self._registry.get_schema(category, element_type)
        except KeyError:
            return None

    def _model_name(self, base: str) -> str:
        """Generate sanitized model name."""
        name = f"{base}{self.INPUT_SUFFIX}"
        # Sanitize for Python identifier
        result = "".join(
            c if c.isalnum() or c == "_" else "_"
            for c in name
        )
        if result and result[0].isdigit():
            result = "_" + result
        return result or "Model"
