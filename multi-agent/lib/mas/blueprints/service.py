from typing import Any, Dict, List, Optional

from mas.blueprints.models.blueprint import BlueprintSpec, BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.collector import BlueprintConfigCollector
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    BlueprintSaveError,
    BlueprintMetadataError,
)
from mas.core.identity import Identity
from mas.core.ref import RefWalker
from mas.elements.common.card import ElementCard
from mas.elements.common.validator import ValidationContext
from mas.catalog.card_service import ElementCardService
from mas.validation.models import BlueprintValidationResult
from mas.validation.service import ElementValidationService


class BlueprintService:
    def __init__(
        self,
        repo: BlueprintRepository,
        resolver: BlueprintResolver,
        validation_service: ElementValidationService = None,
        card_service: ElementCardService = None,
        auth_service=None,
    ):
        self._repo = repo
        self._resolver = resolver
        self._validation_service = validation_service
        self._card_service = card_service
        self._auth_service = auth_service
        self._config_collector = BlueprintConfigCollector()

    def set_auth_service(self, auth_service) -> None:
        """Late-bind the auth service (created after BlueprintService in the container)."""
        self._auth_service = auth_service

    # ────────── Write ──────────
    def save_draft(self, *, identity: Identity, draft_dict: dict,
                   metadata: Optional[Dict[str, Any]] = None) -> str:
        draft_bp = BlueprintDraft(**draft_dict)
        rid_refs = list(RefWalker.external_rids(draft_bp))
        return self._repo.save(identity=identity, spec=draft_bp,
                               rid_refs=rid_refs, metadata=metadata or {})

    # ────────── Single-blueprint reads (ID is globally unique) ──────────
    def load_draft(self, blueprint_id: str) -> BlueprintDraft:
        doc = self._repo.load(blueprint_id)
        return BlueprintDraft(**doc.spec_dict)

    def get_blueprint_draft_doc(self, blueprint_id: str) -> BlueprintDocument:
        """Get blueprint document with metadata for sharing operations."""
        return self._repo.load(blueprint_id)

    def update_draft(self, *, blueprint_id: str, draft_dict: dict) -> bool:
        if not self._repo.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)
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
        """Draft -> JSON-serialisable dict (no meta)."""
        return self.load_draft(blueprint_id).model_dump(mode="json")

    def exists(self, blueprint_id: str) -> bool:
        return self._repo.exists(blueprint_id)

    def delete(self, blueprint_id: str) -> bool:
        return self._repo.delete(blueprint_id)

    def load_many(self, blueprint_ids: List[str]) -> List[BlueprintDocument]:
        """Load multiple blueprint documents by their IDs in a single operation."""
        return self._repo.load_many(blueprint_ids)

    # ────────── Bulk listing / counting (optionally per identity) ──────────
    def list_ids(self, *, identity: Optional[Identity] = None, **pg) -> List[str]:
        return self._repo.list_ids(identity=identity, **pg)

    def list_summaries(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[BlueprintSummary]:
        """Return lightweight blueprint summaries (no full spec)."""
        return self._repo.list_summaries(identity=identity, **pg)

    def list_draft_dicts(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[Dict[str, Any]]:
        """
        Return pure-dict drafts (as saved) in one DB round-trip.
        """
        docs = self._repo.list_docs(identity=identity, **pg)
        return [doc.spec_dict for doc in docs]

    def list_draft_docs(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[BlueprintDocument]:
        """
        Return blueprint documents (as saved) in one DB round-trip.
        """
        return self._repo.list_docs(identity=identity, **pg)

    def _resolve_doc(self, doc: BlueprintDocument) -> BlueprintDocument:
        """Resolve a single document's spec_dict from draft to fully resolved form."""
        draft = BlueprintDraft(**doc.spec_dict)
        resolved_spec = self._resolver.resolve(draft)
        return doc.model_copy(update={"spec_dict": resolved_spec.model_dump(mode="json")})

    def list_resolved_docs(
            self, *, identity: Optional[Identity] = None, **pg
    ) -> List[BlueprintDocument]:
        """
        Return documents with resolved spec_dict instead of draft spec_dict.
        """
        docs = self._repo.list_docs(identity=identity, **pg)
        resolved_docs = []

        for doc in docs:
            try:
                resolved_docs.append(self._resolve_doc(doc))
            except Exception as e:
                print(f"Skipping blueprint '{doc.blueprint_id}': resolution failed — {e}")
                continue

        return resolved_docs

    def get_resolved_doc(self, blueprint_id: str) -> BlueprintDocument:
        """
        Return a single document with its spec_dict resolved.

        Raises:
            BlueprintNotFoundError: If the blueprint does not exist.
        """
        if not self.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)
        doc = self._repo.load(blueprint_id)
        return self._resolve_doc(doc)

    def count(self, *, identity: Optional[Identity] = None) -> int:
        return self._repo.count(identity=identity)

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
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> BlueprintValidationResult:
        """
        Validate all elements in a saved blueprint.
        
        Args:
            blueprint_id: Blueprint ID to validate
            user_id: Logged-in user (for auth-aware validators)
            timeout_seconds: Timeout for network checks
            
        Returns:
            BlueprintValidationResult with all element results
            
        Raises:
            RuntimeError: If validation service not configured
            KeyError: If blueprint not found
        """
        self._ensure_validation_service()
        spec = self.load_resolved(blueprint_id)
        return self._validate_spec(
            spec, blueprint_id, timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    def validate_draft(
        self,
        draft_dict: dict,
        user_id: str = "",
        timeout_seconds: float = 10.0,
        credential_user_id: str = "",
    ) -> BlueprintValidationResult:
        """
        Validate a blueprint draft before saving.

        This validates a blueprint YAML/JSON without requiring it to be saved first.
        Useful for UI validation before creating a blueprint.
        """
        self._ensure_validation_service()
        spec = self.resolve_draft_dict(draft_dict)
        return self._validate_spec(
            spec, "draft", timeout_seconds,
            user_id=user_id, credential_user_id=credential_user_id,
        )

    # ────────── Card Building ──────────
    def get_blueprint_cards(
        self,
        blueprint_id: str,
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for all elements in a saved blueprint.
        """
        self._ensure_card_service()
        spec = self.load_resolved(blueprint_id)
        return self._build_cards_from_spec(spec)

    def get_draft_cards(
        self,
        draft_dict: dict
    ) -> Dict[str, ElementCard]:
        """
        Get element cards for a blueprint draft.
        """
        self._ensure_card_service()
        spec = self.resolve_draft_dict(draft_dict)
        return self._build_cards_from_spec(spec)

    # ────────── Helpers ──────────
    def _ensure_validation_service(self) -> None:
        """Raise if validation service not configured."""
        if self._validation_service is None:
            raise RuntimeError("ValidationService not configured")

    def _ensure_card_service(self) -> None:
        """Raise if card service not configured."""
        if self._card_service is None:
            raise RuntimeError("CardService not configured")

    def _validate_spec(
        self,
        spec: BlueprintSpec,
        blueprint_id: str,
        timeout_seconds: float,
        user_id: str = "",
        credential_user_id: str = "",
    ) -> BlueprintValidationResult:
        """Collect configs from spec, validate, and build result."""
        configs = self._config_collector.collect(spec)
        context = ValidationContext(
            timeout_seconds=timeout_seconds,
            user_id=user_id,
            credential_user_id=credential_user_id,
            auth_service=self._auth_service,
        )
        results = self._validation_service.validate_ordered(configs, context)
        return BlueprintValidationResult(
            blueprint_id=blueprint_id,
            is_valid=all(r.is_valid for r in results.values()),
            element_results=results,
        )

    def _build_cards_from_spec(
        self,
        spec: BlueprintSpec,
    ) -> Dict[str, ElementCard]:
        """Collect configs from spec and build cards."""
        configs = self._config_collector.collect(spec)
        return self._card_service.build_all_cards(configs)
