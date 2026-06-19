"""BlueprintService — application-layer orchestrator for the Blueprint bounded context.

Sits between the inbound adapters (Flask routes) and the outbound adapters
(MongoDB repositories).  All external dependencies are injected so the
service can be exercised in unit tests with in-memory fakes.

GENIE-1336
----------
* ``update_draft`` uses OCC write + pre-update snapshot (requires
  ``version_repo``).
* New public methods: ``list_versions``, ``load_version``, ``restore_version``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

_logger = logging.getLogger(__name__)

from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    ConcurrentModificationError,
    DuplicateSnapshotError,
    FeatureNotConfiguredError,
    VersionNotFoundError,
)
from mas.blueprints.models.blueprint import BlueprintDocument, Identity
from mas.blueprints.models.blueprint_version import BlueprintVersionDocument
from mas.blueprints.repository.repository import BlueprintRepository
from mas.blueprints.repository.version_repository import (
    BlueprintVersionRepository,
)


class BlueprintService:
    """
    Application service orchestrating all blueprint use-cases.

    Parameters
    ----------
    repo:
        Primary blueprint repository (required).
    resolver:
        Dependency resolver for external ``$ref`` values (optional, may be
        ``None`` in minimal deployments).
    validation_service:
        Validates a draft spec before persistence (optional).
    card_service:
        Manages linked card data (optional).
    auth_service:
        Checks access permissions (optional).
    version_repo:
        Append-only version snapshot repository (GENIE-1336).  Required
        for ``update_draft`` and all version-history methods.  When
        ``None``, those methods raise ``FeatureNotConfiguredError``.
    """

    def __init__(
        self,
        repo: BlueprintRepository,
        resolver: Any = None,
        validation_service: Any = None,
        card_service: Any = None,
        auth_service: Any = None,
        version_repo: BlueprintVersionRepository | None = None,
    ) -> None:
        self._repo = repo
        self._resolver = resolver
        self._validation_service = validation_service
        self._card_service = card_service
        self._auth_service = auth_service
        self._version_repo = version_repo

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create_blueprint(
        self,
        identity: Identity,
        spec_dict: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Persist a new blueprint and return its generated ``blueprint_id``.

        ``rid_refs`` are extracted from ``spec_dict`` automatically.
        """
        rid_refs = self._extract_rid_refs(spec_dict)
        return self._repo.save(
            identity=identity,
            spec=spec_dict,
            rid_refs=rid_refs,
            metadata=metadata or {},
        )

    def create_draft(
        self,
        identity: Identity,
        draft_dict: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Create a new blueprint draft and return its generated ``blueprint_id``.

        This is a convenience alias for ``create_blueprint()`` that accepts
        the ``draft_dict`` parameter name used by the versioning regression
        tests and future API callers.

        Parameters
        ----------
        identity:
            Owner identity (user or team).
        draft_dict:
            Full spec dict for the new blueprint.
        metadata:
            Optional metadata sub-document.
        """
        return self.create_blueprint(
            identity=identity,
            spec_dict=draft_dict,
            metadata=metadata or {},
        )

    def update_draft(
        self,
        blueprint_id: str,
        draft_dict: dict[str, Any],
        user_id: str = "",
        change_summary: str | None = None,
    ) -> bool:
        """
        Update the live spec of an existing blueprint using OCC +
        pre-update snapshot.

        Parameters
        ----------
        blueprint_id:
            Target blueprint.
        draft_dict:
            Full replacement spec dict.
        user_id:
            Identifier of the caller, recorded in the snapshot.
        change_summary:
            Optional human-readable description of the change (≤ 500 chars).

        Returns
        -------
        bool
            Always ``True`` on success; exceptions are raised on failure.

        Raises
        ------
        FeatureNotConfiguredError
            If ``version_repo`` is not configured.
        BlueprintNotFoundError
            If the blueprint does not exist.
        ConcurrentModificationError
            If another writer modified the blueprint between the read and
            the write.
        """
        self._require_version_repo()

        rid_refs = self._extract_rid_refs(draft_dict)

        # OCC + snapshot path.
        current_doc = self._load_document_or_raise(blueprint_id)

        # Snapshot the current state BEFORE writing the new one so that
        # even if the write fails the pre-edit state is preserved.
        self._snapshot_version(
            doc=current_doc,
            user_id=user_id,
            change_summary=change_summary,
        )

        new_version = self._repo.update_with_version(
            blueprint_id=blueprint_id,
            spec=draft_dict,
            rid_refs=rid_refs,
            expected_version=current_doc.version,
        )

        if new_version is None:
            raise ConcurrentModificationError(
                blueprint_id=blueprint_id,
                expected_version=current_doc.version,
            )

        return True

    def load_blueprint(self, blueprint_id: str) -> BlueprintDocument:
        """Load the full blueprint document or raise ``BlueprintNotFoundError``."""
        return self._load_document_or_raise(blueprint_id)

    def delete_blueprint(self, blueprint_id: str) -> bool:
        """Hard-delete a blueprint by ID."""
        return self._repo.delete(blueprint_id)

    def set_metadata(self, blueprint_id: str, metadata: dict[str, Any]) -> bool:
        """Replace the metadata sub-document."""
        return self._repo.set_metadata(blueprint_id, metadata)

    def list_blueprints(
        self,
        identity: Identity | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[BlueprintDocument]:
        """Return a paginated list of full blueprint documents."""
        return self._repo.list_docs(identity=identity, skip=skip, limit=limit)

    def count_blueprints(self, identity: Identity | None = None) -> int:
        """Return total blueprint count, optionally filtered by identity."""
        return self._repo.count(identity=identity)

    # ------------------------------------------------------------------
    # Version-history operations  (GENIE-1336)
    # ------------------------------------------------------------------

    def list_versions(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> dict[str, Any]:
        """
        Return a paginated list of version summaries for a blueprint.

        Parameters
        ----------
        blueprint_id:
            Target blueprint (must exist).
        page:
            1-based page number; clamped to ≥ 1.
        page_size:
            Items per page; clamped to [1, 100].

        Returns
        -------
        dict with keys:
            ``items``, ``total``, ``page``, ``page_size``, ``total_pages``.

        Raises
        ------
        BlueprintNotFoundError
            If the blueprint does not exist.
        FeatureNotConfiguredError
            If ``version_repo`` was not injected (feature not configured).
        """
        self._require_version_repo()
        self._require_blueprint_exists(blueprint_id)

        # Clamp pagination parameters.
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        items, total = self._version_repo.find_by_blueprint_id(  # type: ignore[union-attr]
            blueprint_id=blueprint_id,
            page=page,
            page_size=page_size,
        )

        total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1

        return {
            "items": [item.to_summary() for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def load_version(
        self,
        blueprint_id: str,
        version_number: int,
    ) -> dict[str, Any]:
        """
        Return the full detail of a specific blueprint version.

        The response includes ``spec_dict_snapshot``.

        Raises
        ------
        BlueprintNotFoundError
            If the parent blueprint does not exist.
        VersionNotFoundError
            If no snapshot exists for ``version_number``.
        FeatureNotConfiguredError
            If the version repo is not configured.
        """
        self._require_version_repo()
        self._require_blueprint_exists(blueprint_id)

        version_doc = self._version_repo.find_one(blueprint_id, version_number)  # type: ignore[union-attr]
        if version_doc is None:
            raise VersionNotFoundError(blueprint_id, version_number)

        return version_doc.to_detail()

    def restore_version(
        self,
        blueprint_id: str,
        target_version: int,
        user_id: str = "",
    ) -> bool:
        """
        Restore the live blueprint spec to the snapshot captured at
        ``target_version``.

        Steps
        -----
        1. Load the target snapshot → raises ``VersionNotFoundError`` if absent.
        2. Delegate to ``update_draft`` with the snapshot's ``spec_dict_snapshot``
           and an auto-generated ``change_summary`` of
           ``"Restored to version <N>"``.

        The ``update_draft`` call will:
        * Snapshot the current (pre-restore) state first.
        * Apply the OCC-guarded write.

        This means no history is ever lost — every restore is itself
        reversible via another restore call.

        Raises
        ------
        BlueprintNotFoundError
            If the parent blueprint does not exist.
        VersionNotFoundError
            If the target version snapshot does not exist.
        ConcurrentModificationError
            If another writer modified the blueprint between the read and
            the restore write.
        FeatureNotConfiguredError
            If the version repo is not configured.
        """
        self._require_version_repo()

        # Raises BlueprintNotFoundError if blueprint absent.
        self._load_document_or_raise(blueprint_id)

        # Raises VersionNotFoundError if snapshot absent.
        snapshot = self._version_repo.find_one(blueprint_id, target_version)  # type: ignore[union-attr]
        if snapshot is None:
            raise VersionNotFoundError(blueprint_id, target_version)

        change_summary = f"Restored to version {target_version}"

        return self.update_draft(
            blueprint_id=blueprint_id,
            draft_dict=snapshot.spec_dict_snapshot,
            user_id=user_id,
            change_summary=change_summary,
        )

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------

    def _extract_rid_refs(self, spec_dict: dict[str, Any]) -> list[str]:
        """
        Recursively extract all ``$ref`` values from a spec dict.

        Deduplicates the result so each rid appears at most once.
        """
        refs: list[str] = []
        self._walk_refs(spec_dict, refs)
        # Preserve order but deduplicate.
        seen = set()
        unique: list[str] = []
        for ref in refs:
            if ref not in seen:
                seen.add(ref)
                unique.append(ref)
        return unique

    def _walk_refs(self, node: Any, acc: list[str]) -> None:
        """DFS traversal collecting ``$ref`` string values."""
        if isinstance(node, dict):
            if "$ref" in node and isinstance(node["$ref"], str):
                acc.append(node["$ref"])
            for value in node.values():
                self._walk_refs(value, acc)
        elif isinstance(node, list):
            for item in node:
                self._walk_refs(item, acc)

    def _require_blueprint_exists(self, blueprint_id: str) -> None:
        """Raise ``BlueprintNotFoundError`` if the blueprint does not exist."""
        if not self._repo.exists(blueprint_id):
            raise BlueprintNotFoundError(blueprint_id)

    def _load_document_or_raise(self, blueprint_id: str) -> BlueprintDocument:
        """Load a ``BlueprintDocument`` or raise ``BlueprintNotFoundError``."""
        try:
            doc = self._repo.load(blueprint_id)
        except KeyError as exc:
            # Repository raises KeyError for missing docs; re-raise as domain error.
            raise BlueprintNotFoundError(blueprint_id) from exc
        if doc is None:
            raise BlueprintNotFoundError(blueprint_id)
        return doc

    def _snapshot_version(
        self,
        doc: BlueprintDocument,
        user_id: str = "",
        change_summary: str | None = None,
    ) -> None:
        """
        Insert an immutable snapshot of ``doc``'s current spec.

        Silently ignores ``DuplicateSnapshotError`` — this makes the
        operation idempotent (the snapshot already exists) and non-fatal.
        The OCC guard (``update_with_version`` returning ``None``) is the
        authoritative safety net.  All other exceptions are propagated.
        """
        try:
            version_doc = BlueprintVersionDocument(
                blueprint_id=doc.blueprint_id,
                version=doc.version,
                spec_dict_snapshot=doc.spec_dict,
                created_by=user_id,
                change_summary=change_summary,
            )
            self._version_repo.insert_snapshot(version_doc)  # type: ignore[union-attr]
        except DuplicateSnapshotError:
            # Snapshot already exists — idempotent by design, non-fatal.
            _logger.debug("Snapshot insert skipped (duplicate)", exc_info=True)

    def _require_version_repo(self) -> None:
        """Raise ``FeatureNotConfiguredError`` if ``BlueprintVersionRepository`` is not configured."""
        if self._version_repo is None:
            raise FeatureNotConfiguredError("BlueprintVersionRepository")
