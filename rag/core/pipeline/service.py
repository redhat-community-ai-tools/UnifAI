"""Pipeline application service - CRUD and business logic."""
from datetime import datetime
from typing import Optional, Dict, Any, Union

from core.pipeline.domain.model import PipelineRecord, PipelineStatus, PipelineStats
from core.pipeline.domain.repository import PipelineRepository


class PipelineService:
    """Application service for Pipeline aggregate."""

    def __init__(self, pipeline_repo: PipelineRepository):
        self._repo = pipeline_repo

    # --- CRUD ---
    def get(self, pipeline_id: str) -> Optional[PipelineRecord]:
        """Get a pipeline record by ID."""
        return self._repo.find_by_id(pipeline_id)

    def delete(self, pipeline_id: str) -> int:
        """Delete pipeline record(s). Returns count deleted."""
        return self._repo.delete(pipeline_id)

    # --- Business Methods ---
    def register(self, pipeline_id: str, source_type: str) -> PipelineRecord:
        """Create new pipeline record if doesn't exist, otherwise update timestamp."""
        existing = self._repo.find_by_id(pipeline_id)
        if existing:
            existing.last_updated = datetime.utcnow()
            self._repo.save(existing)
            return existing

        record = PipelineRecord(
            pipeline_id=pipeline_id,
            source_type=source_type,
            status=PipelineStatus.PENDING,
            created_at=datetime.utcnow(),
            last_updated=datetime.utcnow(),
            stats=PipelineStats(),
        )
        self._repo.save(record)
        return record

    def update_status(
        self,
        pipeline_id: str,
        status: Union[PipelineStatus, str],
    ) -> bool:
        """
        Update pipeline status with automatic timestamp and processing time calculation.
        
        Args:
            pipeline_id: The pipeline ID
            status: PipelineStatus enum or string value
        """
        # Convert string to enum if needed
        if isinstance(status, str):
            status = PipelineStatus(status)

        record = self._repo.find_by_id(pipeline_id)
        if not record:
            return False

        record.status = status
        record.last_updated = datetime.utcnow()

        # Calculate processing time when done
        if status == PipelineStatus.DONE:
            record.stats.processing_time = (
                record.last_updated - record.created_at
            ).total_seconds()

        self._repo.save(record)
        return True

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
        return self._repo.increment_stats(pipeline_id, stats_updates)
