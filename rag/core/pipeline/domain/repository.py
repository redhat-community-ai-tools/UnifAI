"""Pipeline repository port (interface)."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from core.pipeline.domain.model import PipelineRecord, PipelineStatus


class PipelineRepository(ABC):
    """Port for PipelineRecord persistence."""

    @abstractmethod
    def find_by_id(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Get pipeline record by ID."""
        ...

    @abstractmethod
    def save(self, record: PipelineRecord) -> None:
        """Insert or update pipeline record (upsert by pipeline_id)."""
        ...

    @abstractmethod
    def update_status(self, pipeline_id: str, status: PipelineStatus) -> bool:
        """Update pipeline status. Returns True if updated."""
        ...

    @abstractmethod
    def get_stats_batch(self, pipeline_ids: List[str]) -> Dict[str, PipelineRecord]:
        """Batch fetch pipeline records for enrichment."""
        ...

    @abstractmethod
    def delete(self, pipeline_id: str) -> int:
        """Delete pipeline(s). Returns count deleted."""
        ...

    @abstractmethod
    def increment_stats(self, pipeline_id: str, stats_updates: Dict[str, Any]) -> bool:
        """
        Increment pipeline statistics atomically.
        
        Args:
            pipeline_id: The pipeline ID
            stats_updates: Dict of stat field names to increment values
                          e.g. {"documents_retrieved": 5, "chunks_generated": 10}
        
        Returns:
            True if updated successfully
        """
        ...

    @abstractmethod
    def get_source_stats(self, source_type: str) -> Dict[str, Any]:
        """
        Get aggregated statistics for a specific source type.
        
        Args:
            source_type: The source type to get statistics for
            
        Returns:
            Dictionary containing aggregated statistics including:
            - total_pipelines: Total count of pipelines
            - active_pipelines: Count of active pipelines
            - completed_pipelines: Count of done pipelines
            - failed_pipelines: Count of failed pipelines
            - pending_pipelines: Count of pending pipelines
            - latest_update: Most recent update timestamp
        """
        ...
