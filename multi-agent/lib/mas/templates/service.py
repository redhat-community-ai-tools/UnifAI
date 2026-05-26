"""
Template Service - Public facade for template operations.

Single Responsibility: Orchestrate template CRUD, schema generation, and instantiation.
Dependency Inversion: Depends on abstractions (repository interface, element registry).
"""
from typing import List, Dict, Any, Optional, Tuple
from uuid import uuid4
from datetime import datetime, timezone

from mas.core.identity import Identity, IdentityType
from mas.blueprints.models.blueprint import BlueprintDraft
from mas.catalog.element_registry import ElementRegistry
from mas.templates.repository.repository import TemplateRepository
from mas.templates.models.template import (
    Template,
    TemplateSummary,
    PlaceholderMeta,
    TemplateMetadata,
    InputValidationResult,
    MaterializeResult,
)
from mas.templates.schema.analyzer import PlaceholderAnalyzer
from mas.templates.instantiation.instantiator import (
    TemplateInstantiator,
    InstantiationResult,
)
from mas.templates.instantiation.materializer import (
    ResourceMaterializer,
    MaterializationResult,
)
from mas.templates.errors import (
    TemplateNotFoundError,
    TemplateSaveError,
    InstantiationError,
    MergeError,
)


class TemplateService:
    """
    Public facade for template operations.
    
    Orchestrates:
    - Template CRUD operations
    - Input schema generation
    - Template instantiation
    - Blueprint and resource materialization
    
    All external interactions go through this service.
    
    Dependencies (injected):
    - TemplateRepository: Template persistence
    - ElementRegistry: Element schema lookups
    - BlueprintService (optional): For saving instantiated blueprints
    - ResourcesService (optional): For saving instantiated resources
    """

    def __init__(
            self,
            repository: TemplateRepository,
            element_registry: ElementRegistry,
            blueprint_service=None,  # Optional: BlueprintService
            resources_service=None,  # Optional: ResourcesService
    ):
        self._repo = repository
        self._element_registry = element_registry
        self._blueprint_service = blueprint_service
        self._resources_service = resources_service

        # Internal components
        self._analyzer = PlaceholderAnalyzer(element_registry)
        self._instantiator = TemplateInstantiator()

    # ─────────────────────────────────────────────────────────────────────
    #  Template CRUD
    # ─────────────────────────────────────────────────────────────────────
    def create_template(
            self,
            draft: Dict[str, Any],
            placeholders: Dict[str, Any],
            metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create a new template from raw dicts.
        
        Args:
            draft: The template blueprint dict (BlueprintDraft format)
            placeholders: Placeholder metadata dict (PlaceholderMeta format)
            metadata: Optional template metadata dict
            
        Returns:
            Generated template ID
        """
        template_id = str(uuid4())

        template = Template(
            template_id=template_id,
            draft=BlueprintDraft(**draft),
            placeholders=PlaceholderMeta(**placeholders),
            metadata=TemplateMetadata(**(metadata or {})),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        return self._repo.save(template)

    def get_template(self, template_id: str) -> Template:
        """
        Get a template by ID.
        
        Raises TemplateNotFoundError if not found.
        """
        try:
            return self._repo.get(template_id)
        except KeyError:
            raise TemplateNotFoundError(template_id)

    def update_template(self, template: Template) -> bool:
        """
        Update an existing template.
        
        Returns True if modified.
        Raises TemplateNotFoundError if not found.
        """
        try:
            template.updated_at = datetime.now(timezone.utc)
            return self._repo.update(template)
        except KeyError:
            raise TemplateNotFoundError(template.template_id)

    def delete_template(self, template_id: str) -> bool:
        """
        Delete a template.
        
        Returns True if deleted.
        Raises TemplateNotFoundError if not found.
        """
        try:
            return self._repo.delete(template_id)
        except KeyError:
            raise TemplateNotFoundError(template_id)

    def exists(self, template_id: str) -> bool:
        """Check if template exists."""
        return self._repo.exists(template_id)

    # ─────────────────────────────────────────────────────────────────────
    #  Template Listing
    # ─────────────────────────────────────────────────────────────────────
    def list_templates(
            self,
            *,
            is_public: Optional[bool] = True,
            category: Optional[str] = None,
            tags: Optional[List[str]] = None,
            skip: int = 0,
            limit: int = 100,
    ) -> List[Template]:
        """
        List templates with optional filtering.
        
        Default: returns only public templates.
        """
        return self._repo.list_templates(
            is_public=is_public,
            category=category,
            tags=tags,
            skip=skip,
            limit=limit,
        )

    def search_templates(
            self,
            query: str,
            *,
            limit: int = 20,
    ) -> List[Template]:
        """Search templates by name/description."""
        return self._repo.search(query, is_public=True, limit=limit)

    def search_template_summaries(
            self,
            query: str,
            *,
            limit: int = 20,
    ) -> List[TemplateSummary]:
        """Search templates and return summaries."""
        templates = self.search_templates(query=query, limit=limit)
        return [TemplateSummary.from_template(t) for t in templates]

    def count_templates(
            self,
            *,
            is_public: Optional[bool] = True,
            category: Optional[str] = None,
    ) -> int:
        """Count templates matching criteria."""
        return self._repo.count(is_public=is_public, category=category)

    # ─────────────────────────────────────────────────────────────────────
    #  Input Schema Generation
    # ─────────────────────────────────────────────────────────────────────
    def get_input_schema(self, template_id: str) -> Dict[str, Any]:
        """
        Get the input schema for a template as JSON Schema.
        
        Returns a complete JSON Schema with all field definitions,
        types, constraints, and $defs for complex types.
        
        The schema is generated by Pydantic from the exact field
        definitions in the element config schemas.
        """
        template = self.get_template(template_id)
        return self._analyzer.get_json_schema(template)

    def validate_input(
            self,
            template_id: str,
            user_input: Dict[str, Any],
    ) -> InputValidationResult:
        """
        Validate user input against the template's input schema.
        
        Args:
            template_id: Template to validate against
            user_input: User-provided input values

        Returns:
            InputValidationResult with is_valid and errors

        Raises:
            TemplateNotFoundError: If template not found
        """
        template = self.get_template(template_id)
        input_model = self._analyzer.create_input_model(template)

        try:
            input_model(**user_input)
            return InputValidationResult(is_valid=True, errors=[])
        except Exception as e:
            return InputValidationResult(is_valid=False, errors=[str(e)])

    # ─────────────────────────────────────────────────────────────────────
    #  Template Instantiation
    # ─────────────────────────────────────────────────────────────────────
    def instantiate(
            self,
            template_id: str,
            user_input: Dict[str, Any],
    ) -> InstantiationResult:
        """
        Instantiate a template with user input.
        
        Returns InstantiationResult containing:
        - blueprint: The merged BlueprintDraft
        - template_id: Source template ID
        - filled_fields: List of fields that were filled
        
        Raises InstantiationError if instantiation fails.
        """
        template = self.get_template(template_id)

        try:
            return self._instantiator.instantiate(template, user_input)
        except MergeError as e:
            raise InstantiationError(str(e), errors=e.errors)
        except Exception as e:
            raise InstantiationError(f"Instantiation failed: {str(e)}")

    # ─────────────────────────────────────────────────────────────────────
    #  Full Materialization (Blueprint + Resources)
    # ─────────────────────────────────────────────────────────────────────
    def materialize(
            self,
            template_id: str,
            identity: Identity,
            user_input: Dict[str, Any],
            blueprint_name: Optional[str] = None,
            save_resources: bool = True,
            skip_validation: bool = False,
    ) -> MaterializeResult:
        """
        Instantiate template and save blueprint + resources to user's account.
        
        This is the main entry point for template usage.
        
        Args:
            template_id: Template to instantiate
            identity: Identity who owns the result
            user_input: User-provided values
            blueprint_name: Optional name override
            save_resources: If True, save resources and create $refs (default)
            skip_validation: If True, skip blueprint validation (default False)
            
        Returns:
            MaterializeResult with blueprint_id, resource_ids, and metadata
            
        Raises:
            InstantiationError: If instantiation or validation fails
            RuntimeError: If required services not configured
        """
        if self._blueprint_service is None:
            raise RuntimeError("BlueprintService not configured")

        if save_resources and self._resources_service is None:
            raise RuntimeError("ResourcesService not configured but save_resources=True")

        # Instantiate template
        template = self.get_template(template_id)
        try:
            result = self._instantiator.instantiate(template, user_input)
        except MergeError as e:
            raise InstantiationError(str(e), errors=e.errors)

        if blueprint_name:
            result.blueprint.name = blueprint_name

        # Validate
        if not skip_validation:
            self._validate_blueprint(result.blueprint)

        # Save blueprint (and optionally resources)
        blueprint_id, resource_ids = self._save_blueprint(
            blueprint=result.blueprint,
            template=template,
            identity=identity,
            save_resources=save_resources,
        )

        return MaterializeResult(
            blueprint_id=blueprint_id,
            template_id=template_id,
            fields_filled=result.field_count,
            name=result.blueprint.name,
            resources_created=len(resource_ids),
            resource_ids=resource_ids,
        )

    def _validate_blueprint(self, blueprint: BlueprintDraft) -> None:
        """Validate blueprint, raise InstantiationError if invalid."""
        result = self._blueprint_service.validate_draft(
            blueprint.model_dump(mode="json")
        )
        if not result.is_valid:
            failed = [r for r in result.element_results.values() if not r.is_valid]
            raise InstantiationError(
                f"Blueprint validation failed for {len(failed)} element(s)",
                errors=failed,
            )

    def _save_blueprint(
            self,
            blueprint: BlueprintDraft,
            template: Template,
            identity: Identity,
            save_resources: bool,
    ) -> Tuple[str, List[str]]:
        """Save blueprint (and optionally resources). Returns (blueprint_id, resource_ids)."""
        metadata = {
            "source": "template",
            "template_id": template.template_id,
            "template_name": template.name,
        }

        if save_resources and self._resources_service is not None:
            materializer = ResourceMaterializer(self._resources_service)
            mat_result = materializer.materialize(blueprint, identity)

            blueprint_id = self._blueprint_service.save_draft(
                identity=identity,
                draft_dict=mat_result.blueprint_draft.model_dump(mode="json"),
                metadata=metadata,
            )
            return blueprint_id, mat_result.resource_ids
        else:
            blueprint_id = self._blueprint_service.save_draft(
                identity=identity,
                draft_dict=blueprint.model_dump(mode="json"),
                metadata=metadata,
            )
            return blueprint_id, []

    # ─────────────────────────────────────────────────────────────────────
    #  Utility Methods
    # ─────────────────────────────────────────────────────────────────────
    def get_template_summary(self, template_id: str) -> TemplateSummary:
        """Get a summary of template for catalog display."""
        template = self.get_template(template_id)
        return TemplateSummary.from_template(template)

    def list_template_summaries(
            self,
            *,
            is_public: Optional[bool] = True,
            category: Optional[str] = None,
            tags: Optional[List[str]] = None,
            skip: int = 0,
            limit: int = 100,
    ) -> List[TemplateSummary]:
        """Get summaries for template listing."""
        templates = self.list_templates(
            is_public=is_public,
            category=category,
            tags=tags,
            skip=skip,
            limit=limit,
        )
        return [TemplateSummary.from_template(t) for t in templates]
