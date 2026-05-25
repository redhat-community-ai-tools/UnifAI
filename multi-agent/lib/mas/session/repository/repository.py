from abc import ABC, abstractmethod
from typing import List, Mapping, Any, Dict, Optional
from datetime import datetime
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.models import SessionChat, TimeSeriesPoint, SystemAnalyticsData
from mas.core.identity import Identity
from mas.core.dto import GroupedCount


class SessionRepository(ABC):
    """
    Abstract persistence API for session records.

    Owner-scoped methods accept an ``Identity`` (user or team) rather than
    a raw ``user_id`` string so that team-owned sessions are properly
    isolated from personal ones.
    """

    @abstractmethod
    def save(self, record: SessionRecord) -> None:
        """Persist a session record (create or update)."""
        ...

    @abstractmethod
    def fetch(self, run_id: str) -> SessionRecord:
        """Load a session record by run_id."""
        ...

    @abstractmethod
    def fetch_chat(self, run_id: str) -> SessionChat:
        """Fetch only messages and output from a session's graph state (projected)."""
        ...

    @abstractmethod
    def list_runs(self, identity: Identity) -> List[str]:
        """Return all run_ids owned by the given identity."""
        ...

    @abstractmethod
    def list_docs(self, identity: Identity) -> List[Mapping[str, Any]]:
        """Return all session documents for an identity in a single query."""
        ...

    @abstractmethod
    def delete(self, run_id: str) -> bool:
        """Delete a session by run_id. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    def count(self, identity: Identity, filter: Dict[str, Any]) -> int:
        """Count sessions matching filter criteria for an identity."""
        ...
    
    @abstractmethod
    def group_count(
        self,
        identity: Identity,
        group_by: List[str],
        filter: Dict[str, Any] = None
    ) -> List[GroupedCount]:
        """
        Group documents by specified fields and return counts.
        Implementation should perform efficient server-side grouping.

        Args:
            identity: The owning identity (user or team) to filter by
            group_by: List of field names to group by
            filter: Optional additional filter criteria

        Returns:
            List of GroupedCount DTOs with grouped field values and count.
            Example: [GroupedCount(fields={"blueprint_id": "bp-123"}, count=10), ...]
        """
        ...

    # ---------- System-wide methods (for admin analytics) ----------

    @abstractmethod
    def count_system(self, since: Optional[datetime] = None) -> int:
        """
        Count all sessions system-wide (no user_id constraint).
        
        Args:
            since: Optional cutoff datetime - only count sessions started after this time
            
        Returns:
            Total count of matching sessions
        """
        ...

    @abstractmethod
    def get_distinct_identities(self, since: Optional[datetime] = None) -> List[Dict[str, str]]:
        """Get distinct (type, id) pairs from all sessions.

        Returns a list of ``{"type": "user"|"team", "id": "..."}`` dicts
        so that callers can distinguish users from teams with the same id.
        """
        ...

    @abstractmethod
    def group_count_system(
        self,
        group_by: List[str],
        since: Optional[datetime] = None
    ) -> List[GroupedCount]:
        """
        Group all sessions by specified fields and return counts (system-wide).
        No user_id constraint - for admin analytics.
        
        Args:
            group_by: List of field names to group by
            since: Optional cutoff datetime - only include sessions started after this time
            
        Returns:
            List of GroupedCount DTOs with grouped field values and count.
        """
        ...

    @abstractmethod
    def get_session_activity_series(
        self,
        since: Optional[datetime] = None
    ) -> List[TimeSeriesPoint]:
        """
        Get session activity data grouped by appropriate time intervals.

        The implementation determines the appropriate time granularity
        (hourly, daily, monthly) based on the time range.

        Args:
            since: Optional cutoff datetime - only include sessions started after this time.
                   None means all-time data.
            
        Returns:
            List of TimeSeriesPoint with period labels and session counts,
            sorted chronologically.
        """
        ...

    @abstractmethod
    def get_system_analytics(
        self,
        since: Optional[datetime] = None
    ) -> SystemAnalyticsData:
        """
        Get aggregated system analytics data for admin dashboards.

        Returns grouped session data for building user activity and
        top blueprints views. Implementations should optimize for
        efficiency (e.g., batching multiple aggregations).
        
        Args:
            since: Optional cutoff datetime - only include sessions started after this time
            
        Returns:
            SystemAnalyticsData containing user and blueprint groupings.
        """
        ...

    @abstractmethod
    def delete_by_identity(self, identity: Identity) -> int:
        """Delete all sessions owned by *identity*.  Returns the count of deleted documents."""
        ...
