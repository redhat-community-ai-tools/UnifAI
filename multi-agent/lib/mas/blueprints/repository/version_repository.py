"""Abstract port (interface) for the Blueprint Version repository.

The ``blueprint_versions`` collection is append-only — no updates or
deletes are permitted at the domain level.  This makes the version history
an immutable audit trail.

GENIE-1336
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from mas.blueprints.models.blueprint_version import BlueprintVersionDocument


class BlueprintVersionRepository(ABC):
    """
    Abstract port for the append-only version-snapshot store.

    Concrete implementations are adapter-layer concerns
    (e.g. ``MongoBlueprintVersionRepository``).
    """

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    @abstractmethod
    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        """
        Persist an immutable version snapshot.

        Assigns ``version_doc._id`` on the domain object after insert so the
        caller gets the generated primary key without a separate round-trip.

        Raises
        ------
        DuplicateSnapshotError
            If a snapshot for ``(blueprint_id, version)`` already exists.
            The service layer silently swallows this for idempotency.
        """

    @abstractmethod
    def ensure_indexes(self) -> None:
        """
        Idempotently create all necessary indexes on the backing store.

        Should be called once at application start-up (e.g. from the DI
        container) and is safe to call on an already-indexed collection.
        """

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @abstractmethod
    def find_by_blueprint_id(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[BlueprintVersionDocument], int]:
        """
        Return a paginated list of version summaries (newest first).

        ``spec_dict_snapshot`` is **excluded** from the returned objects to
        keep list responses lightweight.  Use ``find_one`` to fetch the full
        snapshot for a single version.

        Parameters
        ----------
        blueprint_id:
            Parent blueprint.
        page:
            1-based page number.
        page_size:
            Items per page (the caller is responsible for clamping to a
            sensible maximum).

        Returns
        -------
        tuple[list[BlueprintVersionDocument], int]
            ``(items, total_count)`` — total_count is the total number of
            versions for this blueprint (unaffected by pagination).
        """

    @abstractmethod
    def find_one(
        self,
        blueprint_id: str,
        version: int,
    ) -> BlueprintVersionDocument | None:
        """
        Return the full version document (including ``spec_dict_snapshot``)
        for a specific ``(blueprint_id, version)`` pair, or ``None`` if it
        does not exist.
        """
