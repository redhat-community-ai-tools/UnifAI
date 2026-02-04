"""MongoDB adapter for MonitoringRepository port."""
from datetime import datetime
from typing import List, Dict, Any

from pymongo.database import Database

from core.monitoring.domain.model import MetricsEntry, ErrorEntry, LogEntry
from core.monitoring.domain.repository import MonitoringRepository


class MongoMonitoringRepository(MonitoringRepository):
    """
    MongoDB implementation of the MonitoringRepository port.
    
    Manages three collections: metrics, errors, logs.
    """

    def __init__(self, database: Database):
        """
        Initialize the MongoDB monitoring repository.
        
        Args:
            database: MongoDB database instance (e.g., client["pipeline_monitoring"])
        """
        self._db = database
        self._metrics = database.metrics
        self._errors = database.errors
        self._logs = database.logs
        
        # Ensure indexes for performance
        self._metrics.create_index("pipeline_id")
        self._errors.create_index("pipeline_id")
        self._logs.create_index([("source_type", 1), ("timestamp", -1)])
        self._logs.create_index("pipeline_id")

    # --- Metrics ---
    def save_metrics(self, entry: MetricsEntry) -> None:
        """Save a metrics snapshot."""
        doc = entry.to_dict()
        doc["timestamp"] = datetime.now()
        self._metrics.insert_one(doc)

    def get_metrics(self, pipeline_id: str, limit: int = 100) -> List[MetricsEntry]:
        """Get metrics history for a specific pipeline."""
        docs = self._metrics.find(
            {"pipeline_id": pipeline_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return [MetricsEntry.from_dict(doc) for doc in docs]

    # --- Errors ---
    def save_error(self, entry: ErrorEntry) -> None:
        """Save an error record."""
        doc = entry.to_dict()
        doc["timestamp"] = datetime.utcnow()
        self._errors.insert_one(doc)

    def get_errors(self, pipeline_id: str, limit: int = 100) -> List[ErrorEntry]:
        """Get error history for a specific pipeline."""
        docs = self._errors.find(
            {"pipeline_id": pipeline_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return [ErrorEntry.from_dict(doc) for doc in docs]

    # --- Logs ---
    def save_log(self, entry: LogEntry) -> None:
        """Save a log entry."""
        doc = entry.to_dict()
        self._logs.insert_one(doc)

    def get_logs_by_source(self, source_type: str, limit: int = 10) -> List[LogEntry]:
        """Get recent logs for a specific source type."""
        docs = self._logs.find(
            {"source_type": source_type},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return [LogEntry.from_dict(doc) for doc in docs]

    def get_logs_by_pipeline(self, pipeline_id: str, limit: int = 100) -> List[LogEntry]:
        """Get logs for a specific pipeline."""
        docs = self._logs.find(
            {"pipeline_id": pipeline_id},
            {"_id": 0}
        ).sort("timestamp", -1).limit(limit)
        
        return [LogEntry.from_dict(doc) for doc in docs]

