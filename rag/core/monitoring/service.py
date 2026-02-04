"""Monitoring application service - log processing and metrics tracking."""
from datetime import datetime
import logging
from collections import deque
from typing import Dict, List, Optional, Any

from core.monitoring.domain.model import MetricsEntry, ErrorEntry, LogEntry
from core.monitoring.domain.repository import MonitoringRepository
from core.pipeline.domain.repository import PipelineRepository

from core.monitoring.parsing.base import LogParser
from core.data_sources.types.slack.log_parser import SlackLogParser
from core.data_sources.types.document.log_parser import DocLogParser


class MonitoringService:
    """
    Application service for pipeline monitoring.
    
    Handles log processing, metrics tracking, and provides monitoring
    capabilities through the MonitoringRepository port.
    """
    
    def __init__(
        self,
        monitoring_repo: MonitoringRepository,
        pipeline_repo: PipelineRepository,
    ):
        """
        Initialize the monitoring service.
        
        Args:
            monitoring_repo: Repository for metrics/errors/logs persistence
            pipeline_repo: Repository for pipeline record access
        """
        self._monitoring_repo = monitoring_repo
        self._pipeline_repo = pipeline_repo
        self._logger = logging.getLogger(__name__)
        
        # In-memory cache of recent logs for quick access
        self._recent_logs_cache: Dict[str, deque] = {}
        
        # Handler reference for cleanup
        self._monitoring_handler: Optional[logging.Handler] = None
        self._monitoring_logger: Optional[logging.Logger] = None

    def log_metrics(self, pipeline_id: str, metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics for a pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            metrics: Dictionary containing metrics data
        """
        pipeline = self._pipeline_repo.find_by_id(pipeline_id)
        if not pipeline:
            self._logger.warning(f"Attempted to log metrics for non-existent pipeline: {pipeline_id}")
            return
        
        print(f"Logging metrics for pipeline {pipeline_id}: {metrics}")
        
        # Increment pipeline stats
        self._pipeline_repo.increment_stats(pipeline_id, metrics)
        
        # Save metrics snapshot
        entry = MetricsEntry(
            pipeline_id=pipeline_id,
            source_type=pipeline.source_type,
            metrics=metrics,
        )
        self._monitoring_repo.save_metrics(entry)
        self._logger.info(f"Logged metrics for pipeline {pipeline_id}: {metrics}")

    def record_error(
        self,
        pipeline_id: str,
        error_message: str,
        error_details: Optional[Dict] = None,
    ) -> None:
        """
        Record an error that occurred during pipeline execution.
        
        Args:
            pipeline_id: The ID of the pipeline where the error occurred
            error_message: A descriptive error message
            error_details: Optional dictionary with additional error details
        """
        pipeline = self._pipeline_repo.find_by_id(pipeline_id)
        if not pipeline:
            self._logger.warning(f"Attempted to record error for non-existent pipeline: {pipeline_id}")
            return
        
        entry = ErrorEntry(
            pipeline_id=pipeline_id,
            source_type=pipeline.source_type,
            error_message=error_message,
            error_details=error_details or {},
        )
        self._monitoring_repo.save_error(entry)
        self._logger.error(f"Error in pipeline {pipeline_id}: {error_message}")

    def get_source_stats(self, source_type: str) -> Dict:
        """
        Get aggregated statistics for a specific source type.
        
        Args:
            source_type: The source type to get statistics for
            
        Returns:
            Dictionary containing aggregated statistics
        """
        return self._pipeline_repo.get_source_stats(source_type)

    def get_recent_activity(self, source_type: str, limit: int = 10) -> List[str]:
        """
        Get recent log entries for a specific source type.
        
        Args:
            source_type: The source type to get logs for
            limit: Maximum number of log entries to return
            
        Returns:
            List of log message strings
        """
        logs = self._monitoring_repo.get_logs_by_source(source_type, limit)
        return [log.message for log in logs]

    def process_log_line(self, log_line: str, pipeline_id: Optional[str] = None) -> None:
        """
        Process a log line to extract monitoring information.
        
        Args:
            log_line: A string containing a log entry
            pipeline_id: Optional pipeline ID. If None, will attempt to extract from log
        """
        timestamp, module, level, message = LogParser.parse_log_line(log_line)
        
        # Determine source type from log content
        source_type = self._detect_source_type(message, pipeline_id, module)
        
        # Extract pipeline ID if not provided
        if not pipeline_id:
            pipeline_id = self._extract_pipeline_id(log_line, source_type)
        
        # Update recent logs cache
        if source_type not in self._recent_logs_cache:
            self._recent_logs_cache[source_type] = deque(maxlen=10)
        self._recent_logs_cache[source_type].appendleft(log_line)
        
        # Store log entry
        log_entry = LogEntry(
            source_type=source_type,
            message=message,
            level=level,
            module=module,
            timestamp=timestamp,
            pipeline_id=pipeline_id,
        )
        self._monitoring_repo.save_log(log_entry)
        
        # Extract and update metrics
        metrics = self._extract_metrics(log_line, source_type)
        if metrics and pipeline_id:
            self.log_metrics(pipeline_id, metrics)

    def _detect_source_type(self, message: str, pipeline_id: Optional[str], module: str) -> str:
        """Detect source type from log content."""
        if "Slack" in message or (pipeline_id and 'slack' in pipeline_id):
            return "SLACK"
        elif "document" in message.lower() or "pdf" in message.lower() or "docx" in message.lower() or module.startswith("docling"):
            return "DOCUMENT"
        return "OTHER"

    def _extract_pipeline_id(self, log_line: str, source_type: str) -> Optional[str]:
        """Extract pipeline ID from log line based on source type."""
        if source_type == "SLACK":
            channel_id = SlackLogParser.extract_slack_channel_id(log_line)
            if channel_id:
                return f"slack_{channel_id}"
        elif source_type == "DOCUMENT":
            doc_id = DocLogParser.extract_doc_id(log_line)
            if doc_id:
                return f"doc_{doc_id}"
        return None

    def _extract_metrics(self, log_line: str, source_type: str) -> Dict[str, Any]:
        """Extract metrics from log line."""
        metrics: Dict[str, Any] = {}
        
        # Process based on source type
        if source_type == "SLACK":
            # Count API calls
            api_endpoint = SlackLogParser.extract_api_endpoint(log_line)
            if api_endpoint:
                metrics["api_calls"] = 1
            
            # Track message counts
            message_count = SlackLogParser.extract_message_count(log_line)
            if message_count:
                metrics["documents_retrieved"] = message_count
        
        elif source_type == "DOCUMENT":
            # For document pipelines, each pipeline represents one document
            if "Processing document" in log_line or "Started processing" in log_line:
                metrics["documents_retrieved"] = 1
            
            # Count API calls for document processing
            api_endpoint = DocLogParser.extract_api_endpoint(log_line)
            if api_endpoint:
                metrics["api_calls"] = 1
            
            # Track chunk counts (document-specific patterns)
            chunk_count = DocLogParser.extract_chunk_count(log_line)
            if chunk_count:
                metrics["chunks_generated"] = chunk_count
            
            # Track embedding counts (document-specific patterns)
            embedding_count = DocLogParser.extract_embedding_count(log_line)
            if embedding_count:
                metrics["embeddings_created"] = embedding_count
        
        # Generic patterns (base LogParser)
        chunk_count = LogParser.extract_chunk_count(log_line)
        if chunk_count and "chunks_generated" not in metrics:
            metrics["chunks_generated"] = chunk_count
        
        embedding_count = LogParser.extract_embedding_count(log_line)
        if embedding_count and "embeddings_created" not in metrics:
            metrics["embeddings_created"] = embedding_count
        
        return metrics

    def start_log_monitoring(self, pipeline_id: str = "", target_logger: Optional[logging.Logger] = None) -> None:
        """
        Start monitoring a logger for pipeline information.
        
        This method adds a custom handler to the logger to capture log messages
        directly without needing a file.
        
        Args:
            pipeline_id: Optional pipeline ID to associate with all logs
            target_logger: The logger instance to monitor (default: uses internal logger)
        """
        if target_logger is None:
            target_logger = self._logger
        
        self._logger.info(f"Starting log monitoring for logger: {target_logger.name}")
        
        service = self
        
        class MonitoringHandler(logging.Handler):
            def __init__(self):
                super().__init__()
            
            def emit(self, record: logging.LogRecord) -> None:
                log_line = self.format(record)
                service.process_log_line(log_line, pipeline_id)
        
        handler = MonitoringHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        target_logger.addHandler(handler)
        
        self._monitoring_handler = handler
        self._monitoring_logger = target_logger

    def finish_log_monitoring(self) -> None:
        """Turn off monitoring a logger for pipeline information."""
        if self._monitoring_handler and self._monitoring_logger:
            self._monitoring_logger.removeHandler(self._monitoring_handler)
            self._monitoring_handler = None
            self._monitoring_logger = None
            self._logger.info("Finished log monitoring")
