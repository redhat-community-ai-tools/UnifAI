from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from mas.blueprints.models.blueprint import BlueprintDraft, BlueprintDocument, BlueprintSummary


class BlueprintRepository(ABC):
    # ────────────────────────────── Writes ──────────────────────────────
    @abstractmethod
    def save(self, user_id, spec: BlueprintDraft, rid_refs: list[str], metadata: Dict[str, Any]) -> str:
        """
        Persist `spec` for the given user and return the generated blueprint_id.
        """

    @abstractmethod
    def update(self, *, blueprint_id: str, spec: BlueprintDraft,
               rid_refs: list[str]) -> bool:
        """
        Replace an existing draft.  Return True if a document was modified.
        """

    @abstractmethod
    def set_metadata(self, *, blueprint_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Set the metadata dictionary for a blueprint document.
        Return True if a document was modified.
        """

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
            self,
            *,
            user_id: Optional[str] = None,
            skip: int = 0,
            limit: int = 100,
            sort_desc: bool = True,
    ) -> List[str]:
        """
        Return blueprint IDs, optionally restricted to `user_id`, with pagination.
        """

    @abstractmethod
    def list_docs(
            self,
            *,
            user_id: Optional[str] = None,
            skip: int = 0,
            limit: int = 100,
            sort_desc: bool = True,
    ) -> List[BlueprintDocument]:
        """
        Return blueprint documents, optionally restricted to `user_id`,
        with pagination.
        """

    @abstractmethod
    def list_summaries(
            self,
            *,
            user_id: Optional[str] = None,
            skip: int = 0,
            limit: int = 100,
            sort_desc: bool = True,
    ) -> List[BlueprintSummary]:
        """
        Return lightweight blueprint summaries (id, name, description,
        timestamps, metadata) without the full spec.
        """

    @abstractmethod
    def list_direct_usage(self, rid: str) -> List[str]:
        """
        Return blueprint IDs whose *catalogue entries* contain `rid`
        directly.  Nested refs inside resources are not covered here;
        those are handled by ResourceRepository.list_nested_usage().
        """

    @abstractmethod
    def count_usage(self, rid: str) -> int:
        """
        Count how many blueprints (optionally belonging to `user_id`) reference a
        given resource ID `rid`.
        """

    @abstractmethod
    def count(self, user_id: Optional[str] = None) -> int:
        """
        Return the total number of blueprints, or the number belonging to
        `user_id` if provided.
        """
