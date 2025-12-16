from abc import ABC, abstractmethod
from typing import List, Dict, Any
from resources.models import ResourceDoc, ResourceQuery
from core.dto import GroupedCount


class ResourceRepository(ABC):
    @abstractmethod
    def save(self, doc: ResourceDoc) -> str:
        """Insert a new resource document."""
        ...

    @abstractmethod
    def update(self, doc: ResourceDoc) -> str:
        """Update an existing resource document."""
        ...

    @abstractmethod
    def get(self, rid: str) -> ResourceDoc:
        """Retrieve a resource document by ID."""
        ...

    @abstractmethod
    def delete(self, rid: str) -> None:
        """Delete a resource document by ID."""
        ...

    @abstractmethod
    def find_by_name(self, user_id: str, category: str, type: str, name: str) -> ResourceDoc | None:
        """Find a resource document by alias."""
        ...

    @abstractmethod
    def find_resources(self, query: ResourceQuery) -> List[ResourceDoc]:
        """Find resources based on query criteria with pagination."""
        ...

    @abstractmethod
    def count_resources(self, query: ResourceQuery) -> int:
        """Count resources matching query criteria."""
        ...

    @abstractmethod
    def count(self, user_id: str, filter: dict) -> int:
        """Count documents matching a filter."""
        ...

    @abstractmethod
    def meta(self, rid: str) -> tuple[str, str]: ...

    @abstractmethod
    def count_nested(self, rid: str) -> int: ...

    @abstractmethod
    def list_nested_usage(self, rid: str) -> List[str]:
        """
        Return resource IDs whose `nested_refs` array contains `rid`
        (i.e. the resource depends on `rid` inside its own config).
        """

    @abstractmethod
    def exists(self, rid: str) -> bool: ...

    @abstractmethod
    def group_count(
        self, 
        user_id: str, 
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.
        Implementation should perform efficient server-side grouping.
        
        Args:
            user_id: The user ID to filter by
            group_by: List of field names to group by
            filter: Optional additional filter criteria
            
        Returns:
            List of GroupedCount DTOs with grouped field values and count.
            Example: [GroupedCount(fields={"category": "llm"}, count=5), ...]
        """
        ...
