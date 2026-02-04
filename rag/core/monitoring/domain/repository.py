"""Monitoring repository port (interface)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from core.monitoring.domain.model import MetricsEntry, ErrorEntry, LogEntry


class MonitoringRepository(ABC):
    """
    Port for monitoring data persistence.
    
    Handles metrics, errors, and logs related to pipeline execution.
    """

    # --- Metrics ---
    @abstractmethod
    def save_metrics(self, entry: MetricsEntry) -> None:
        """
        Save a metrics snapshot.
        
        Args:
            entry: The metrics entry to save
        """
        ...

    @abstractmethod
    def get_metrics(self, pipeline_id: str, limit: int = 100) -> List[MetricsEntry]:
        """
        Get metrics history for a specific pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            limit: Maximum number of entries to return
            
        Returns:
            List of metrics entries, most recent first
        """
        ...

    # --- Errors ---
    @abstractmethod
    def save_error(self, entry: ErrorEntry) -> None:
        """
        Save an error record.
        
        Args:
            entry: The error entry to save
        """
        ...

    @abstractmethod
    def get_errors(self, pipeline_id: str, limit: int = 100) -> List[ErrorEntry]:
        """
        Get error history for a specific pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            limit: Maximum number of entries to return
            
        Returns:
            List of error entries, most recent first
        """
        ...

    # --- Logs ---
    @abstractmethod
    def save_log(self, entry: LogEntry) -> None:
        """
        Save a log entry.
        
        Args:
            entry: The log entry to save
        """
        ...

    @abstractmethod
    def get_logs_by_source(self, source_type: str, limit: int = 10) -> List[LogEntry]:
        """
        Get recent logs for a specific source type.
        
        Args:
            source_type: The source type to filter by
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries, most recent first
        """
        ...

    @abstractmethod
    def get_logs_by_pipeline(self, pipeline_id: str, limit: int = 100) -> List[LogEntry]:
        """
        Get logs for a specific pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            limit: Maximum number of entries to return
            
        Returns:
            List of log entries, most recent first
        """
        ...

