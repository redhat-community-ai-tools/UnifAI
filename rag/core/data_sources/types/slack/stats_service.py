"""Slack statistics aggregation service."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.data_sources.service import DataSourceService


# Active statuses that match the UI definition
ACTIVE_STATUSES: Set[str] = {"RUNNING", "PENDING", "QUEUED"}


@dataclass
class SlackStats:
    """Slack statistics for dashboard."""
    id: int
    total_channels: int
    active_channels: int
    total_messages: int
    api_calls_count: int
    last_sync_at: Optional[str]
    total_embeddings: int
    updated_at: str
    
    def to_dict(self) -> dict:
        """Convert to dictionary for API responses (camelCase for frontend)."""
        return {
            "id": self.id,
            "totalChannels": self.total_channels,
            "activeChannels": self.active_channels,
            "totalMessages": self.total_messages,
            "apiCallsCount": self.api_calls_count,
            "lastSyncAt": self.last_sync_at,
            "totalEmbeddings": self.total_embeddings,
            "updatedAt": self.updated_at,
        }


class SlackStatsService:
    """
    Application service for Slack statistics aggregation.
    
    Query use case that aggregates stats from DataSourceService for Slack sources.
    Provides channel counts, message totals, API call counts, and sync timestamps.
    
    Usage:
        service = SlackStatsService(data_source_service)
        stats = service.get_stats()
        print(f"Active channels: {stats.active_channels}")
    """
    
    def __init__(self, data_source_service: DataSourceService):
        """
        Initialize with injected DataSourceService.
        
        Args:
            data_source_service: Service for accessing data source information
        """
        self._source_service = data_source_service
    
    def get_stats(self) -> SlackStats:
        """
        Get aggregated Slack statistics.
        
        Returns:
            SlackStats with channel counts, messages, API calls, and timestamps
        """
        sources = self._source_service.list_with_stats("SLACK")
        
        counts = self._aggregate_counts(sources)
        last_sync = self._get_last_sync_at(sources)
        
        return SlackStats(
            id=1,
            total_channels=counts["total_channels"],
            active_channels=counts["active_channels"],
            total_messages=counts["total_messages"],
            api_calls_count=counts["api_calls_count"],
            last_sync_at=last_sync,
            total_embeddings=len(sources),
            updated_at=datetime.utcnow().isoformat() + "Z",
        )
    
    def _aggregate_counts(self, sources: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Compute channel counts, message totals, and API calls.
        
        Args:
            sources: List of source dictionaries with pipeline stats
            
        Returns:
            Dictionary with aggregated counts
        """
        total_channels = len(sources)
        active_channels = sum(
            1 for s in sources 
            if s.get("status") in ACTIVE_STATUSES
        )
        total_messages = sum(
            s.get("pipeline_stats", {}).get("documents_retrieved", 0) 
            for s in sources if s.get("pipeline_stats")
        )
        api_calls_count = sum(
            s.get("pipeline_stats", {}).get("api_calls", 0) 
            for s in sources if s.get("pipeline_stats")
        )
        
        return {
            "total_channels": total_channels,
            "active_channels": active_channels,
            "total_messages": total_messages,
            "api_calls_count": api_calls_count,
        }
    
    def _get_last_sync_at(self, sources: List[Dict[str, Any]]) -> Optional[str]:
        """
        Get most recent sync timestamp across all sources.
        
        Args:
            sources: List of source dictionaries
            
        Returns:
            ISO timestamp string of most recent sync, or None
        """
        timestamps = [
            s.get("last_sync_at") 
            for s in sources 
            if s.get("last_sync_at") is not None
        ]
        return max(timestamps) if timestamps else None
