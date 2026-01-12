from typing import Any, Dict, List, Mapping, Optional

from blueprints.models.blueprint import BlueprintSpec, BlueprintDraft
from blueprints.repository.repository import BlueprintRepository
from blueprints.resolver import BlueprintResolver
from blueprints.validation.collector import BlueprintConfigCollector
from blueprints.exceptions import (
    BlueprintNotFoundError,
    BlueprintSaveError,
    BlueprintMetadataError,
)
from core.ref import RefWalker
from elements.common.validator import ValidationContext
from validation.models import BlueprintValidationResult
from validation.service import ElementValidationService


class BlueprintService:
    def __init__(
        self, 
        repo: BlueprintRepository, 
        resolver: BlueprintResolver,
        validation_service: ElementValidationService = None,
    ):
        self._repo = repo
        self._resolver = resolver
        self._validation_service = validation_service
        self._config_collector = BlueprintConfigCollector()

    # ────────── Write ──────────
    def save_draft(self, *, user_id: str, draft_dict: dict, metadata: Optional[Dict[str, Any]] = None) -> str:
        draft_bp = BlueprintDraft(**draft_dict)
        rid_refs = list(RefWalker.external_rids(draft_bp))
        return self._repo.save(user_id=user_id, spec=draft_bp, rid_refs=rid_refs, metadata=metadata or {})

    # ────────── Single-blueprint reads (ID is globally unique) ──────────
    def load_draft(self, blueprint_id: str) -> BlueprintDraft:
        doc = self._repo.load(blueprint_id)
        return BlueprintDraft(**doc["spec_dict"])

    def get_blueprint_draft_doc(self, blueprint_id: str) -> Mapping[str, Any]:
        """Get blueprint document with metadata for sharing operations."""
        return self._repo.load(blueprint_id)

    def update_draft(self, *, blueprint_id: str, draft_dict: dict) -> bool:  # NEW
        draft = BlueprintDraft(**draft_dict)
        rid_refs = list(RefWalker.external_rids(draft))
        return self._repo.update(
            blueprint_id=blueprint_id, spec=draft, rid_refs=rid_refs
        )

    def load_resolved(self, blueprint_id: str) -> BlueprintSpec:
        return self._resolver.resolve(self.load_draft(blueprint_id))

    def load_draft_from_dict(self, draft_dict: dict) -> BlueprintDraft:
        """Load a BlueprintDraft from a dictionary without saving to database."""
        return BlueprintDraft(**draft_dict)

    def resolve_draft_dict(self, draft_dict: dict) -> BlueprintSpec:
        """Resolve a draft dictionary directly to BlueprintSpec without saving to database."""
        draft_bp = BlueprintDraft(**draft_dict)
        return self._resolver.resolve(draft_bp)

    def to_dict(self, blueprint_id: str) -> Dict[str, Any]:
        """Draft → JSON-serialisable dict (no meta)."""
        return self.load_draft(blueprint_id).model_dump(mode="json")

    def exists(self, blueprint_id: str) -> bool:
        return self._repo.exists(blueprint_id)

    def delete(self, blueprint_id: str) -> bool:
        return self._repo.delete(blueprint_id)

    # ────────── Bulk listing / counting (optionally per user) ──────────
    def list_ids(self, *, user_id: str | None = None, **pg) -> List[str]:
        return self._repo.list_ids(user_id=user_id, **pg)

    def list_draft_dicts(
            self, *, user_id: str | None = None, **pg
    ) -> List[Dict[str, Any]]:
        """
        Return pure-dict drafts (as saved) in one DB round-trip.
        """
        docs = self._repo.list_docs(user_id=user_id, **pg)
        return [doc["spec_dict"] for doc in docs]

    def list_draft_docs(
            self, *, user_id: str | None = None, **pg
    ) -> List[Mapping[str, Any]]:
        """
        Return pure-dict drafts (as saved) in one DB round-trip.
        """
        docs = self._repo.list_docs(user_id=user_id, **pg)
        return [doc for doc in docs]

    def list_resolved_docs(
            self, *, user_id: str | None = None, **pg
    ) -> List[Mapping[str, Any]]:
        """
        Return documents with resolved spec_dict instead of draft spec_dict.
        """
        docs = self._repo.list_docs(user_id=user_id, **pg)
        resolved_docs = []

        for doc in docs:
            try:
                # Create draft from spec_dict
                draft = BlueprintDraft(**doc["spec_dict"])
                # Resolve the draft to BlueprintSpec
                resolved_spec = self._resolver.resolve(draft)
                # Convert resolved spec to dict
                resolved_dict = resolved_spec.model_dump(mode="json")

                # Create new doc with resolved spec_dict
                resolved_doc = dict(doc)  # Copy all fields from original doc
                resolved_doc["spec_dict"] = resolved_dict  # Replace spec_dict with resolved version
                resolved_docs.append(resolved_doc)
            except Exception as e:
                # If resolution fails, skip this document
                continue

        return resolved_docs

    def count(self, *, user_id: str | None = None) -> int:
        return self._repo.count(user_id=user_id)

    @staticmethod
    def get_draft_schema() -> Dict[str, Any]:
        """
        Return the JSON schema of the BlueprintDraft model.
        """
        return BlueprintDraft.model_json_schema()

# ────────── Blueprint Metadata ──────────
    def set_metadata(self, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Set the metadata dictionary for a blueprint.
        
        :param blueprint_id: The blueprint ID
        :param metadata: Dictionary of metadata to set
        :return: True if the document was modified
        :raises BlueprintNotFoundError: If blueprint doesn't exist
        :raises BlueprintMetadataError: If update fails
        """
        if not self.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)
        
        try:
            return self._repo.set_metadata(blueprint_id=blueprint_id, metadata=metadata)
        except Exception as e:
            raise BlueprintMetadataError(blueprint_id, f"Failed to update metadata: {str(e)}")
    # ────────── Validation ──────────
    def validate_blueprint(
        self,
        blueprint_id: str,
        timeout_seconds: float = 10.0,
    ) -> BlueprintValidationResult:
        """
        Validate all elements in a saved blueprint.
        
        Args:
            blueprint_id: Blueprint ID to validate
            timeout_seconds: Timeout for network checks
            
        Returns:
            BlueprintValidationResult with all element results
            
        Raises:
            RuntimeError: If validation service not configured
            KeyError: If blueprint not found
        """
        self._ensure_validation_service()
        spec = self.load_resolved(blueprint_id)
        return self._validate_spec(spec, blueprint_id, timeout_seconds)

    def validate_draft(
        self,
        draft_dict: dict,
        timeout_seconds: float = 10.0,
    ) -> BlueprintValidationResult:
        """
        Validate a blueprint draft before saving.
        
        This validates a blueprint YAML/JSON without requiring it to be saved first.
        Useful for UI validation before creating a blueprint.
        
        Args:
            draft_dict: The blueprint draft as a dictionary
            timeout_seconds: Timeout for network checks
            
        Returns:
            BlueprintValidationResult with all element results
            
        Raises:
            RuntimeError: If validation service not configured
            ValueError: If draft schema validation fails
        """
        self._ensure_validation_service()
        spec = self.resolve_draft_dict(draft_dict)
        return self._validate_spec(spec, "draft", timeout_seconds)

    # ────────── Validation Helpers ──────────
    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if self._validation_service is None:
            raise RuntimeError("ValidationService not configured")

    def _validate_spec(
        self,
        spec: BlueprintSpec,
        blueprint_id: str,
        timeout_seconds: float,
    ) -> BlueprintValidationResult:
        """Collect configs from spec, validate, and build result."""
        configs = self._config_collector.collect(spec)
        context = ValidationContext(timeout_seconds=timeout_seconds)
        results = self._validation_service.validate_ordered(configs, context)
        return BlueprintValidationResult(
            blueprint_id=blueprint_id,
            is_valid=all(r.is_valid for r in results.values()),
            element_results=results,
        )
