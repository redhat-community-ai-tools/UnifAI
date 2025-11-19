from datetime import datetime
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from utils.storage.mongo.mongo_helpers import get_mongo_storage
from config.constants import DataSource, ActivePipelineStatus


@dataclass
class SlackAggregateStats:
    totalChannels: int
    activeChannels: int
    totalMessages: int
    apiCallsCount: int


@dataclass
class SlackStats:
    id: int
    totalChannels: int
    activeChannels: int
    totalMessages: int
    apiCallsCount: int
    lastSyncAt: Optional[str]
    totalEmbeddings: int
    updatedAt: str


class SlackStatsProvider:
    def __init__(self):
        # source_service implements both SourceRepository & PipelineRepository
        self._service = get_mongo_storage()

    def _fetch_slack_sources(self) -> List[Dict[str, Any]]:
        """Fetch all SLACK sources enriched with their last pipeline status."""
        return self._service.list_sources(source_type=DataSource.SLACK.upper_name)

    def _aggregate_counts(
        self, sources: List[Dict[str, Any]]
    ) -> SlackAggregateStats:
        """Compute channel counts, message totals, and api calls."""
        
        # Define active statuses that match the UI definition
        active_statuses = ActivePipelineStatus.values()
        
        total_channels  = len(sources)
        active_channels = sum(1 for s in sources if s.get("status") in active_statuses)
        total_messages  = sum(
            s.get("pipeline_stats", {}).get("documents_retrieved", 0) for s in sources if s.get("pipeline_stats")
        )
        api_calls_count = sum(
            s.get("pipeline_stats", {}).get("api_calls", 0) for s in sources if s.get("pipeline_stats")
        )
        return SlackAggregateStats(
            totalChannels=total_channels,
            activeChannels=active_channels,
            totalMessages=total_messages,
            apiCallsCount=api_calls_count,
        )

    def _get_last_sync_at(self, sources: List[Dict[str, Any]]) -> Optional[str]:
        """Return the most recent last_sync_at timestamp (ISO string)."""
        timestamps = []
        for s in sources:
            last_sync = s.get("last_sync_at")
            if last_sync is not None:
                timestamps.append(last_sync)
        return max(timestamps) if timestamps else None

    def _get_total_embeddings(self) -> int:
        """Get total number of SLACK sources in the database."""
        try:
            # Fetch all SLACK sources (reusing existing method)
            sources = self._fetch_slack_sources()
            
            # Return the count of SLACK sources
            return len(sources)
        except Exception:
            # Return 0 if unable to connect to storage
            return 0

    def get_stats(self) -> SlackStats:
        """Public method: gather everything into a single dict."""
        sources = self._fetch_slack_sources()
        counts = self._aggregate_counts(sources)
        last_sync = self._get_last_sync_at(sources)
        total_embeddings = self._get_total_embeddings()
        return SlackStats(
            id=1,
            totalChannels=counts.totalChannels,
            activeChannels=counts.activeChannels,
            totalMessages=counts.totalMessages,
            apiCallsCount=counts.apiCallsCount,
            lastSyncAt=last_sync,
            totalEmbeddings=total_embeddings,
            updatedAt=datetime.utcnow().isoformat() + "Z",
        )
