from abc import ABC, abstractmethod
from typing import List, Mapping, Any, Dict
from session.workflow_session import WorkflowSession
from core.dto import GroupedCount


class SessionRepository(ABC):
    """
    Abstract persistence API for WorkflowSession snapshots.
    """

    @abstractmethod
    def save(self, session: WorkflowSession) -> None:
        """Persist the given session (create or update)."""
        ...

    @abstractmethod
    def fetch(self, run_id: str) -> Mapping[str, Any]:
        """Fetch session raw doc"""
        ...

    @abstractmethod
    def list_runs(self, user_id: str) -> List[str]:
        """Return all run_ids for the given user."""
        ...

    @abstractmethod
    def delete(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def count(self, user_id: str, filter: Dict[str, Any]) -> int:
        """Count sessions matching filter criteria for a user."""
        ...
    
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
            Example: [GroupedCount(fields={"blueprint_id": "bp-123"}, count=10), ...]
        """
        ...