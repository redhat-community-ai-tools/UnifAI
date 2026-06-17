"""
Port (abstract interface) for the blueprint version snapshot repository — GENIE-1336.

Follows the Ports & Adapters architecture enforced throughout this project:
  Domain / Application layers depend only on this interface.
  Infrastructure adapters (MongoDB, in-memory for tests, …) implement it.
"""

from abc import ABC, abstractmethod
from typing import Optional, Tuple, List

from mas.blueprints.models.blueprint_version import BlueprintVersionDocument


class BlueprintVersionRepository(ABC):
    """Abstract repository for the ``blueprint_versions`` collection.

    All methods are synchronous to match the project's existing pymongo
    (sync) adapter pattern.  Any async adapter must run calls in a thread pool.
    """

    # ── Writes ────────────────────────────────────────────────────────────

    @abstractmethod
    def insert_snapshot(self, version_doc: BlueprintVersionDocument) -> str:
        """Persist an immutable version snapshot.

        Args:
            version_doc: Fully constructed snapshot document.

        Returns:
            The inserted document's ``_id`` (MongoDB ObjectId as string).

        Raises:
            pymongo.errors.DuplicateKeyError: If ``(blueprint_id, version)``
                already exists (unique index violation).
        """

    # ── Reads ─────────────────────────────────────────────────────────────

    @abstractmethod
    def find_by_blueprint_id(
        self,
        blueprint_id: str,
        page: int = 1,
        page_size: int = 20,
    ) -> Tuple[List[BlueprintVersionDocument], int]:
        """Return paginated version summaries sorted by version DESC.

        ``spec_dict_snapshot`` is intentionally **not** loaded here to keep
        list payloads lightweight.  Use :meth:`find_one` for the full snapshot.

        Args:
            blueprint_id: Parent blueprint identifier.
            page: 1-based page number.
            page_size: Items per page (clamped by service layer).

        Returns:
            A ``(versions, total_count)`` tuple where *versions* is the
            current page and *total_count* is the total across all pages.
        """

    @abstractmethod
    def find_one(
        self,
        blueprint_id: str,
        version: int,
    ) -> Optional[BlueprintVersionDocument]:
        """Load a specific version with the full ``spec_dict_snapshot``.

        Returns:
            :class:`BlueprintVersionDocument` or ``None`` if not found.
        """

    # ── Infrastructure ────────────────────────────────────────────────────

    @abstractmethod
    def ensure_indexes(self) -> None:
        """Create required indexes idempotently.  Safe to call on startup."""
