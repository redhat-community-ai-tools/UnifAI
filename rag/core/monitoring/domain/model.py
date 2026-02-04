"""Monitoring domain models."""
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional


@dataclass
class MetricsEntry:
    """
    A snapshot of pipeline metrics at a point in time.
    
    Used for tracking time-series metrics during pipeline execution.
    """
    pipeline_id: str
    source_type: str
    metrics: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsEntry":
        """Create a MetricsEntry from a dictionary."""
        return cls(
            pipeline_id=data.get("pipeline_id", ""),
            source_type=data.get("source_type", ""),
            metrics=data.get("metrics", {}),
            timestamp=data.get("timestamp", datetime.utcnow()),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


@dataclass
class ErrorEntry:
    """
    A record of an error that occurred during pipeline execution.
    """
    pipeline_id: str
    source_type: str
    error_message: str
    error_details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorEntry":
        """Create an ErrorEntry from a dictionary."""
        return cls(
            pipeline_id=data.get("pipeline_id", ""),
            source_type=data.get("source_type", ""),
            error_message=data.get("error_message", ""),
            error_details=data.get("error_details", {}),
            timestamp=data.get("timestamp", datetime.utcnow()),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)


@dataclass
class LogEntry:
    """
    A parsed log entry from pipeline execution.
    """
    source_type: str
    message: str
    level: str
    module: str
    timestamp: datetime
    pipeline_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create a LogEntry from a dictionary."""
        return cls(
            source_type=data.get("source_type", ""),
            message=data.get("message", ""),
            level=data.get("level", ""),
            module=data.get("module", ""),
            timestamp=data.get("timestamp", datetime.utcnow()),
            pipeline_id=data.get("pipeline_id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return asdict(self)

