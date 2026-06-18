from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintDocument, BlueprintSummary
from mas.core.identity import Identity


class BlueprintRepository(ABC):
    # ────────────────────────────── Writes ──────────────────────────────
    @abstractmethod
    def save(self, identity: Identity, spec: BlueprintDraft,
             rid_refs: list[str], metadata: Dict[str, Any]) -> str:
        """Persist *spec* owned by *identity* and return the generated blueprint_id."""

    @abstractmethod
    def update(self, *, blueprint_id: str, spec: BlueprintDraft,
               rid_refs: list[str]) -> bool:
        """Replace an existing draft.  Return True if a document was modified."""

    @abstractmethod
    def update_with_version(
        self,
        blueprint_id: str,
        spec: BlueprintDraft,
        rid_refs: list[str],
        expected_version: int,
    ) -> Optional[int]:
        """
        Atomic OCC-guarded spec update.

        Applies ``spec`` only if the document's current ``version`` equals
        ``expected_version``.  On success, increments the version and returns
        the new version number.  Returns ``None`` when the document was not
        found or the version guard failed (concurrent modification).
        """

    @abstractmethod
    def set_metadata(self, *, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """Set the metadata dictionary for a blueprint document."""

    # ────────────────────────────── Reads by ID ─────────────────────────
    @abstractmethod
    def load(self, blueprint_id: str) -> BlueprintDocument:
        """Load a blueprint document by its globally-unique ID or raise `KeyError`."""

    @abstractmethod
    def delete(self, blueprint_id: str) -> bool:
        """Delete by ID.  Return `True` iff a document was removed."""

    @abstractmethod
    def exists(self, blueprint_id: str) -> bool:
        """Return `True` if that ID is present in the store."""

    @abstractmethod
    def load_many(self, blueprint_ids: List[str]) -> List[BlueprintDocument]:
        """Load multiple blueprint documents by their IDs in a single operation."""

    # ────────────────────────────── Listings / Stats ────────────────────
    @abstractmethod
    def list_ids(
            self, *,
            identity: Optional[Identity] = None,
            skip: int = 0, limit: int = 100, sort_desc: bool = True,
    ) -> List[str]:
        """Return blueprint IDs, optionally scoped to *identity*, with pagination."""

    @abstractmethod
    def list_docs(
            self, *,
            identity: Optional[Identity] = None,
            skip: int = 0, limit: int = 100, sort_desc: bool = True,
    ) -> List[BlueprintDocument]:
        """Return blueprint documents, optionally scoped to *identity*."""

    @abstractmethod
    def list_summaries(
            self, *,
            identity: Optional[Identity] = None,
            skip: int = 0, limit: int = 100, sort_desc: bool = True,
    ) -> List[BlueprintSummary]:
        """Return lightweight blueprint summaries (no full spec)."""

    @abstractmethod
    def list_direct_usage(self, rid: str) -> List[str]:
        """Return blueprint IDs whose catalogue entries contain *rid* directly."""

    @abstractmethod
    def count_usage(self, rid: str) -> int:
        """Count how many blueprints reference a given resource ID *rid*."""

    @abstractmethod
    def count(self, identity: Optional[Identity] = None) -> int:
        """Total blueprint count, optionally scoped to *identity*."""

    @abstractmethod
    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all blueprints owned by *identity*.  Returns the count of deleted documents."""
