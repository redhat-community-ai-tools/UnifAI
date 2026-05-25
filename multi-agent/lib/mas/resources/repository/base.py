from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from mas.resources.models import Resource, ResourceQuery
from mas.core.identity import Identity
from mas.core.dto import GroupedCount


class ResourceRepository(ABC):
    @abstractmethod
    def save(self, doc: Resource) -> str:
        """Insert a new resource document."""
        ...

    @abstractmethod
    def update(self, doc: Resource) -> str:
        """Update an existing resource document."""
        ...

    @abstractmethod
    def get(self, rid: str) -> Resource:
        """Retrieve a resource document by ID."""
        ...

    @abstractmethod
    def delete(self, rid: str) -> None:
        """Delete a resource document by ID."""
        ...

    @abstractmethod
    def find_by_name(self, identity: Identity, category: str,
                     type: str, name: str) -> Resource | None:
        """Find a resource document by owner + category + type + name."""
        ...

    @abstractmethod
    def find_resources(self, query: ResourceQuery) -> List[Resource]:
        """Find resources based on query criteria with pagination."""
        ...

    @abstractmethod
    def count_resources(self, query: ResourceQuery) -> int:
        """Count resources matching query criteria."""
        ...

    @abstractmethod
    def count(self, identity: Identity, filter: dict | None = None) -> int:
        """Count documents matching a filter scoped to *identity*."""
        ...

    @abstractmethod
    def meta(self, rid: str) -> tuple[str, str]: ...

    @abstractmethod
    def count_nested(self, rid: str) -> int: ...

    @abstractmethod
    def list_nested_usage(self, rid: str) -> List[str]:
        """Return resource IDs whose `nested_refs` array contains *rid*."""

    @abstractmethod
    def exists(self, rid: str) -> bool: ...

    @abstractmethod
    def count_by_config_field(
        self,
        identity: Identity,
        field: str,
        value: str,
        exclude_rid: str = "",
    ) -> int:
        """Count resources where cfg_dict.<field> == value for the given owner identity."""
        ...

    @abstractmethod
    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] | None = None,
    ) -> List[GroupedCount]:
        """Group documents by fields and return counts, scoped to *identity*."""
        ...

    @abstractmethod
    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all resources owned by *identity*.  Returns the count of deleted documents."""
        ...
