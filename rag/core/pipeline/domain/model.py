"""Pipeline domain model."""
from dataclasses import dataclass, field, fields, asdict, MISSING
from datetime import datetime
from typing import Dict, Any
from enum import Enum


class PipelineStatus(str, Enum):
    """Enum representing possible pipeline statuses."""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    COLLECTING = "COLLECTING"
    PROCESSING = "PROCESSING"
    CHUNKING_AND_EMBEDDING = "CHUNKING_AND_EMBEDDING"
    STORING = "STORING"
    ORCHESTRATING = "ORCHESTRATING"
    DONE = "DONE"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


@dataclass
class PipelineStats:
    """Statistics for a pipeline execution."""
    documents_retrieved: int = 0
    chunks_generated: int = 0
    embeddings_created: int = 0
    api_calls: int = 0
    processing_time: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineStats":
        """Create a PipelineStats instance from a dictionary."""
        return cls(**{
            f.name: data.get(f.name, f.default)
            for f in fields(cls)
            if f.default is not MISSING
        })

    def to_dict(self) -> Dict[str, Any]:
        """Convert the PipelineStats instance to a dictionary."""
        return asdict(self)


@dataclass
class PipelineRecord:
    """Domain model for pipeline execution tracking."""
    pipeline_id: str
    source_type: str
    status: PipelineStatus
    created_at: datetime
    last_updated: datetime
    stats: PipelineStats = field(default_factory=PipelineStats)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PipelineRecord":
        """Create a PipelineRecord instance from a dictionary."""
        # Handle status parsing
        status_value = data.get("status", "PENDING")
        try:
            status = PipelineStatus(status_value)
        except ValueError:
            status = PipelineStatus.PENDING

        return cls(
            pipeline_id=data.get("pipeline_id", ""),
            source_type=data.get("source_type", ""),
            status=status,
            created_at=data.get("created_at", datetime.utcnow()),
            last_updated=data.get("last_updated", datetime.utcnow()),
            stats=PipelineStats.from_dict(data.get("stats", {}) or {}),
            metadata=data.get("metadata", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the PipelineRecord instance to a dictionary."""
        return {
            "pipeline_id": self.pipeline_id,
            "source_type": self.source_type,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "stats": self.stats.to_dict(),
            "metadata": self.metadata,
        }
