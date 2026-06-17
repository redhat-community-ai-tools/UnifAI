import logging
from typing import Any, Dict, List, Optional

from mas.blueprints.models.blueprint import BlueprintSpec, BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.repository.version_repository import BlueprintVersionRepository
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.collector import BlueprintConfigCollector
from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    BlueprintSaveError,
    BlueprintMetadataError,
    VersionNotFoundError,
    ConcurrentModificationError,
)
from mas.core.identity import Identity
from mas.core.ref import RefWalker
from mas.elements.common.card import ElementCard
from mas.elements.common.validator import ValidationContext
from mas.catalog.card_service import ElementCardService
from mas.validation.models import BlueprintValidationResult
from mas.validation.service import ElementValidationService

logger = logging.getLogger(__name__)


_PAGE_SIZE_MAX = 100  # Hard cap on page_size for version listing


class BlueprintService:
    def __init__(
        self,
        repo: BlueprintRepository,
        resolver: BlueprintResolver,
        validation_service: ElementValidationService = None,
        card_service: ElementCardService = None,
        auth_service=None,
        version_repo: Optional[BlueprintVersionRepository] = None,
    ):
        self._repo = repo
        self._resolver = resolver
        self._validation_service = validation_service
        self._card_service = card_service
        self._auth_service = auth_service
        self._version_repo = version_repo
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

    def update_draft(
        self,
        *,
        blueprint_id: str,
        draft_dict: dict,
        user_id: str = "",
        change_summary: Optional[str] = None,
    ) -> bool:
        """Replace an existing blueprint draft.

        When a :class:`BlueprintVersionRepository` is wired, this method uses
        Optimistic Concurrency Control (OCC): it snapshots the *current* live
        state into ``blueprint_versions`` before atomically writing the new
        state.  If a concurrent writer already bumped the version,
        :class:`~mas.blueprints.exceptions.ConcurrentModificationError` is
        raised and the caller should present a "please refresh" message.

        When no ``version_repo`` is configured the legacy
        :meth:`~adapters.outbound.mongo.blueprint_repository.MongoBlueprintRepository.update`
        path is used (no OCC, no snapshots) for full backward compatibility.

        Args:
            blueprint_id: Target blueprint identifier.
            draft_dict: Full new spec dict to persist.
            user_id: Identity of the requesting user (stored on snapshot).
            change_summary: Optional human-readable description of the change.

        Returns:
            ``True`` on success.

        Raises:
            BlueprintNotFoundError: Blueprint does not exist.
            ConcurrentModificationError: OCC version mismatch (409 territory).
        """
        # ── Load current doc — raises KeyError internally if not found ──────
        try:
            current_doc = self._repo.load(blueprint_id)
        except KeyError:
            raise BlueprintNotFoundError(blueprint_id)

        draft = BlueprintDraft(**draft_dict)
        rid_refs = list(RefWalker.external_rids(draft))

        # ── Legacy path (no version_repo configured) ─────────────────────
        if self._version_repo is None:
            return self._repo.update(
                blueprint_id=blueprint_id, spec=draft, rid_refs=rid_refs
            )

        # ── Versioned path: snapshot current state, then OCC-write new ───
        expected_version = current_doc.version

        # 1. Snapshot the state that is about to be overwritten.
        snapshot = BlueprintVersionDocument(
            blueprint_id=blueprint_id,
            version=expected_version,
            spec_dict_snapshot=current_doc.spec_dict,
            created_by=user_id,
            change_summary=change_summary,
        )
        try:
            self._version_repo.insert_snapshot(snapshot)
        except Exception as exc:
            # DuplicateKeyError means a snapshot for this version already exists
            # (e.g. the service crashed after snapshotting but before writing).
            # It is safe to proceed — the snapshot is already there.
            logger.warning(
                "Snapshot insert skipped for blueprint=%s version=%d: %s",
                blueprint_id,
                expected_version,
                exc,
            )

        # 2. Atomically write new spec + bump version (OCC guard).
        updated_doc = self._repo.update_with_version(
            blueprint_id=blueprint_id,
            spec=draft,
            rid_refs=rid_refs,
            expected_version=expected_version,
        )
        if updated_doc is None:
            # Another writer already incremented the version after we read it.
            raise ConcurrentModificationError(blueprint_id, expected_version)

        logger.debug(
            "Blueprint %s updated: v%d → v%d (user=%s)",
            blueprint_id,
            expected_version,
            updated_doc.version,
            user_id,
        )
        return True

    # ────────── Version History (GENIE-1336) ──────────────────────────────────

    def list_versions(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        """Return a paginated list of version summaries for a blueprint.

        Summaries are lightweight (no ``spec_dict_snapshot``), sorted by
        version descending (newest first).

        Args:
            blueprint_id: Target blueprint identifier.
            page: 1-based page number (clamped to ≥1).
            page_size: Items per page (clamped to 1–:data:`_PAGE_SIZE_MAX`).

        Returns:
            ``{"items": [<summary dicts>], "total": <int>, "page": <int>,
            "page_size": <int>, "total_pages": <int>}``

        Raises:
            BlueprintNotFoundError: Blueprint does not exist.
            RuntimeError: ``version_repo`` is not configured.
        """
        self._ensure_version_repo()
        if not self._repo.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

        page = max(1, page)
        page_size = max(1, min(page_size, _PAGE_SIZE_MAX))

        versions, total = self._version_repo.find_by_blueprint_id(
            blueprint_id, page=page, page_size=page_size
        )
        total_pages = max(1, -(-total // page_size))  # ceiling division
        return {
            "items": [v.to_summary() for v in versions],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def load_version(
        self,
        blueprint_id: str,
        version_number: int,
    ) -> Dict[str, Any]:
        """Load a specific historic version with the full ``spec_dict_snapshot``.

        Args:
            blueprint_id: Target blueprint identifier.
            version_number: The exact version to retrieve.

        Returns:
            Detail dict from :meth:`~mas.blueprints.models.blueprint_version.BlueprintVersionDocument.to_detail`.

        Raises:
            BlueprintNotFoundError: Blueprint does not exist.
            VersionNotFoundError: The requested version snapshot is absent.
            RuntimeError: ``version_repo`` is not configured.
        """
        self._ensure_version_repo()
        if not self._repo.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

        version_doc = self._version_repo.find_one(blueprint_id, version_number)
        if version_doc is None:
            raise VersionNotFoundError(blueprint_id, version_number)

        return version_doc.to_detail()

    def restore_version(
        self,
        blueprint_id: str,
        target_version: int,
        user_id: str = "",
    ) -> bool:
        """Restore a blueprint to a historic version snapshot.

        The restore is itself a regular versioned update — it creates a new
        version that carries the old snapshot's spec.  This means:

        * The current live state is snapshotted first (so it is recoverable).
        * The target version's ``spec_dict_snapshot`` becomes the new live spec.
        * The blueprint's version counter is atomically incremented.

        Args:
            blueprint_id: Target blueprint identifier.
            target_version: The historic version number to restore.
            user_id: Requesting user (logged on the restore snapshot).

        Returns:
            ``True`` on success.

        Raises:
            BlueprintNotFoundError: Blueprint does not exist.
            VersionNotFoundError: The requested version snapshot is absent.
            ConcurrentModificationError: Concurrent writer detected (retry).
            RuntimeError: ``version_repo`` is not configured.
        """
        self._ensure_version_repo()

        # 1. Retrieve the historic snapshot (validates it exists).
        version_doc = self._version_repo.find_one(blueprint_id, target_version)
        if version_doc is None:
            raise VersionNotFoundError(blueprint_id, target_version)

        change_summary = f"Restored to version {target_version}"

        # 2. Run the standard versioned update using the snapshot's spec_dict.
        #    update_draft() handles: load current doc → snapshot → OCC write.
        return self.update_draft(
            blueprint_id=blueprint_id,
            draft_dict=version_doc.spec_dict_snapshot,
            user_id=user_id,
            change_summary=change_summary,
        )

    # ────────── Internal helpers for versioning ────────────────────────────

    def _ensure_version_repo(self) -> None:
        """Raise if the version repository is not configured."""
        if self._version_repo is None:
            raise RuntimeError(
                "BlueprintVersionRepository is not configured. "
                "Wire it via BlueprintService(version_repo=...) at startup."
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
