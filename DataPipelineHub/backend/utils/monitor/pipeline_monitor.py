from datetime import datetime
import re
from typing import Dict, List, Optional, Any
import logging
from collections import deque
from .mongo_db_pipeline_repository import MongoDBPipelineRepository
from .log_parser import LogParser
from .slack.slack_log_parser import SlackLogParser
from .docs.doc_log_parser import DocLogParser
from config.constants import SourceType

class PipelineMonitor():
    """
    Concrete implementation of the pipeline monitoring system.
    
    This class provides comprehensive monitoring capabilities for data pipelines,
    tracking execution statistics, errors, and progress across different data sources.
    """
    
    def __init__(self, mongo_client):
        """
        Initialize the pipeline monitor.
        
        Args:
            mongo_client: MongoDB client instance for data persistence
        """
        self.repository = MongoDBPipelineRepository(mongo_client)
        self.logger = logging.getLogger(__name__)
        
        # In-memory cache of recent logs for quick access
        self.recent_logs_cache = {
            source_type: deque(maxlen=10) for source_type in SourceType
        }
        
        # In-memory stats tracking for performance
        self.stats_cache = {}
        
        # Initialize logging
        # self._setup_logging()
    
    def _setup_logging(self):
        """Configure logging for the pipeline monitor."""
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)
    
    # def register_pipeline(self, pipeline_id: str, source_type: SourceType, source_name: str = "", upload_by: str = "") -> None:
    #     """
    #     Register a new pipeline in the monitoring system.

    #     Args:
    #         pipeline_id: Unique identifier for the pipeline
    #         source_type: Type of data source the pipeline is processing
    #         source_name: Optional name of the data source
    #         upload_by: Optional identifier for the uploading user
    #     """
    #     pipeline_data = {
    #         "pipeline_id": pipeline_id,
    #         "source_type": source_type.value,
    #         "status": PipelineStatus.PENDING.value,
    #         "created_at": datetime.now(),
    #         "last_updated": datetime.now(),
    #         "stats": {
    #             "documents_retrieved": 0,
    #             "chunks_generated": 0,
    #             "embeddings_created": 0,
    #             "api_calls": 0,
    #             "processing_time": 0,
    #         },
    #         **({ "name": source_name } if source_name else {}),
    #         **({ "upload_by": upload_by } if upload_by else {})
    #     }

    #     self.repository.save_pipeline(pipeline_data)
    #     self.logger.info(f"Registered new pipeline: {pipeline_id} for source: {source_type.value}")

    # def update_pipeline_status(self, pipeline_id: str, status: PipelineStatus) -> None:
    #     """
    #     Update the status of a pipeline.
        
    #     Args:
    #         pipeline_id: The ID of the pipeline to update
    #         status: The new status of the pipeline
    #     """
    #     pipeline = self.repository.get_pipeline(pipeline_id)
    #     if not pipeline:
    #         self.logger.warning(f"Attempted to update non-existent pipeline: {pipeline_id}")
    #         return
        
    #     pipeline["status"] = status.value
    #     pipeline["last_updated"] = datetime.now()
        
    #     # If the pipeline is done, calculate the total processing time
    #     if status == PipelineStatus.DONE:
    #         created_at = pipeline.get("created_at", datetime.now())
    #         if isinstance(created_at, str):
    #             created_at = datetime.fromisoformat(created_at)
    #         processing_time = (datetime.now() - created_at).total_seconds()
    #         pipeline["stats"]["processing_time"] = processing_time
        
    #     self.repository.save_pipeline(pipeline)
    #     self.logger.info(f"Updated pipeline {pipeline_id} status to {status.value}")
    
    def log_metrics(self, pipeline_id: str, metrics: Dict[str, Any]) -> None:
        """
        Log performance metrics for a pipeline.
        
        Args:
            pipeline_id: The ID of the pipeline
            metrics: Dictionary containing metrics data
        """
        pipeline = self.repository.get_pipeline(pipeline_id)
        if not pipeline:
            self.logger.warning(f"Attempted to log metrics for non-existent pipeline: {pipeline_id}")
            return
        print(f"Logging metrics for pipeline {pipeline_id}: {metrics}")
        # Update pipeline stats with new metrics
        updated_stats = pipeline.get("stats", {})
        for key, value in metrics.items():
            if key in updated_stats and isinstance(value, (int, float)):
                updated_stats[key] += value
            else:
                updated_stats[key] = value
        
        # Save updated pipeline stats
        pipeline["stats"] = updated_stats
        pipeline["last_updated"] = datetime.now()
        self.repository.save_pipeline(pipeline)
        
        # Save detailed metrics record
        metrics_data = {
            "pipeline_id": pipeline_id,
            "source_type": pipeline["source_type"],
            "metrics": metrics
        }
        self.repository.save_metrics(metrics_data)
        self.logger.info(f"Logged metrics for pipeline {pipeline_id}: {metrics}")
    
    def record_error(self, pipeline_id: str, error_message: str, error_details: Optional[Dict] = None) -> None:
        """
        Record an error that occurred during pipeline execution.
        
        Args:
            pipeline_id: The ID of the pipeline where the error occurred
            error_message: A descriptive error message
            error_details: Optional dictionary with additional error details
        """
        pipeline = self.repository.get_pipeline(pipeline_id)
        if not pipeline:
            self.logger.warning(f"Attempted to record error for non-existent pipeline: {pipeline_id}")
            return
        
        # Update pipeline status to FAILED
        # self.update_pipeline_status(pipeline_id, PipelineStatus.FAILED)
        
        # Save detailed error record
        error_data = {
            "pipeline_id": pipeline_id,
            "source_type": pipeline["source_type"],
            "error_message": error_message,
            "error_details": error_details or {}
        }
        self.repository.save_error(error_data)
        self.logger.error(f"Error in pipeline {pipeline_id}: {error_message}")
    
    # def get_active_pipelines(self, source_type: Optional[SourceType] = None) -> List[Dict]:
    #     """
    #     Get all active pipelines, optionally filtered by source type.
        
    #     Args:
    #         source_type: Optional filter by source type
            
    #     Returns:
    #         List of active pipeline dictionaries
    #     """
    #     return self.repository.get_pipelines_by_status(PipelineStatus.ACTIVE, source_type)
    
    # def get_pipeline_stats(self, pipeline_id: str) -> Dict:
    #     """
    #     Get comprehensive statistics for a specific pipeline.
        
    #     Args:
    #         pipeline_id: The ID of the pipeline
            
    #     Returns:
    #         Dictionary containing pipeline statistics
    #     """
    #     pipeline = self.repository.get_pipeline(pipeline_id)
    #     if not pipeline:
    #         self.logger.warning(f"Attempted to get stats for non-existent pipeline: {pipeline_id}")
    #         return {}
        
    #     # Get the latest metrics and errors
    #     metrics = self.repository.get_pipeline_metrics(pipeline_id, limit=10)
    #     errors = self.repository.get_pipeline_errors(pipeline_id, limit=10)
        
    #     return {
    #         "pipeline_id": pipeline_id,
    #         "source_type": pipeline["source_type"],
    #         "status": pipeline["status"],
    #         "created_at": pipeline["created_at"],
    #         "last_updated": pipeline["last_updated"],
    #         "stats": pipeline.get("stats", {}),
    #         "recent_metrics": metrics,
    #         "recent_errors": errors
    #     }
    
    def get_source_stats(self, source_type: SourceType) -> Dict:
        """
        Get aggregated statistics for a specific source type.
        
        Args:
            source_type: The source type to get statistics for
            
        Returns:
            Dictionary containing aggregated statistics
        """
        return self.repository.get_source_stats(source_type)
    
    def get_recent_activity(self, source_type: SourceType, limit: int = 10) -> List[str]:
        """
        Get recent log entries for a specific source type.
        
        Args:
            source_type: The source type to get logs for
            limit: Maximum number of log entries to return
            
        Returns:
            List of log message strings
        """
        logs = self.repository.get_recent_logs(source_type, limit)
        return [log.get("message", "") for log in logs]
    
    def process_log_line(self, log_line: str, pipeline_id: Optional[str] = None) -> None:
        """
        Process a log line to extract monitoring information.
        
        This method parses a log line, extracts relevant information, and updates
        the monitoring system accordingly.
        
        Args:
            log_line: A string containing a log entry
            pipeline_id: Optional pipeline ID. If None, will attempt to extract from log
        """
        
        timestamp, module, level, message = LogParser.parse_log_line(log_line)
        
        # Identify source type from the log message
        source_type = SourceType.OTHER
        if "Slack" in message or (pipeline_id and 'slack' in pipeline_id):
            source_type = SourceType.SLACK
        elif "Jira" in message:
            source_type = SourceType.JIRA
        elif "document" in message.lower() or "pdf" in message.lower() or "docx" in message.lower() or module.startswith("docling"):
            source_type = SourceType.DOCUMENT
        
        # Extract pipeline ID if not provided
        if not pipeline_id:
            if source_type == SourceType.SLACK:
                # Extract channel ID to identify the pipeline
                channel_id = SlackLogParser.extract_slack_channel_id(log_line)
                if channel_id:
                    pipeline_id = f"slack_{channel_id}"
            elif source_type == SourceType.DOCUMENT:
                # Extract document ID to identify the pipeline
                doc_id = DocLogParser.extract_doc_id(log_line)
                if doc_id:
                    pipeline_id = f"doc_{doc_id}"
        
        # Update recent logs cache
        self.recent_logs_cache[source_type].appendleft(log_line)
        
        # Store log in database
        log_data = {
            "timestamp": timestamp,
            "module": module,
            "level": level,
            "message": message,
            "source_type": source_type.value,
            "pipeline_id": pipeline_id
        }
        self.repository.save_log_entry(log_data)
        
        # # Check if this pipeline is already registered - do this before early return
        # if pipeline_id:
        #     pipeline = self.repository.get_pipeline(pipeline_id)
        #     if not pipeline and ("Starting" in message or "Processing" in message):
        #         # Auto-register new pipeline
        #         self.register_pipeline(pipeline_id, source_type)
            
        
        # Extract and update metrics
        metrics = {}
        
        # Process based on source type
        if source_type == SourceType.SLACK:
            # Count API calls
            api_endpoint = SlackLogParser.extract_api_endpoint(log_line)
            if api_endpoint:
                metrics["api_calls"] = 1
            
            # Track message counts
            message_count = SlackLogParser.extract_message_count(log_line)
            if message_count:
                metrics["documents_retrieved"] = message_count
        
        elif source_type == SourceType.DOCUMENT:
            # For document pipelines, each pipeline represents one document
            if "Processing document" in message or "Started processing" in message:
                metrics["documents_retrieved"] = 1
            
            # Count API calls for document processing
            api_endpoint = DocLogParser.extract_api_endpoint(log_line)
            if api_endpoint:
                metrics["api_calls"] = 1
        
        
        # Track chunk counts
        chunk_count = DocLogParser.extract_chunk_count(log_line)
        if chunk_count:
            metrics["chunks_generated"] = chunk_count
        
        # Track embedding counts
        embedding_count = DocLogParser.extract_embedding_count(log_line)
        if embedding_count:
            metrics["embeddings_created"] = embedding_count

        # # Check for document processing status changes
        # status = DocLogParser.extract_processing_status(log_line)
        # if status:
        #     self.update_pipeline_status(pipeline_id, status)
            
        # Track chunk counts
        chunk_count = LogParser.extract_chunk_count(log_line)
        if chunk_count:
            metrics["chunks_generated"] = chunk_count
        
        # Track embedding counts
        embedding_count = LogParser.extract_embedding_count(log_line)
        if embedding_count:
            metrics["embeddings_created"] = embedding_count
        
        # Update pipeline metrics if any were extracted
        if metrics and pipeline_id:
            self.log_metrics(pipeline_id, metrics)
        
        # Check for status changes (in the future we can handle it by source-specific parser)
        # status = LogParser.extract_pipeline_status(log_line)
        # if status and pipeline_id:
        #     self.update_pipeline_status(pipeline_id, status)
    
    # def start_log_monitoring(self, log_file_path: str):
    #     """
    #     Start monitoring a log file for pipeline information.
        
    #     This method continuously monitors a log file, processes new log lines,
    #     and updates the monitoring system accordingly.
        
    #     Args:
    #         log_file_path: Path to the log file to monitor
    #     """
    #     self.logger.info(f"Starting log monitoring for file: {log_file_path}")
        
    #     with open(log_file_path, 'r') as file:
    #         # Move to the end of the file
    #         file.seek(0, 2)
            
    #         while True:
    #             line = file.readline()
    #             if line:
    #                 self.process_log_line(line)
    #             else:
    #                 time.sleep(0.1)  # Sleep briefly to avoid CPU hogging

    def start_log_monitoring(self, pipeline_id="", target_logger=None):
        """
        Start monitoring a logger for pipeline information.
        
        This method adds a custom handler to the logger to capture log messages
        directly without needing a file.
        
        Args:
            target_logger: The logger instance to monitor (default: None, uses self.logger)
        """
        if target_logger is None:
            target_logger = self.logger
        
        self.logger.info(f"Starting log monitoring for logger: {target_logger.name}")
        
        # Create a custom handler that processes log records
        class MonitoringHandler(logging.Handler):
            def __init__(self, monitor):
                super().__init__()
                self.monitor = monitor
            
            def emit(self, record):
                # Convert the log record to a string format
                log_line = self.format(record)
                # Process the log line directly
                self.monitor.process_log_line(log_line, pipeline_id)
        
        # Create and add our custom handler
        handler = MonitoringHandler(self)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        target_logger.addHandler(handler)

        # Store reference to handler so we can remove it later
        self._monitoring_handler = handler
        self._monitoring_logger = target_logger
        
        # No need for a loop as the handler will be called for each log message

    def finish_log_monitoring(self):
        """
        Turn off monitoring a logger for pipeline information.
        """
        if hasattr(self, "_monitoring_handler") and self._monitoring_handler and self._monitoring_logger:
            self._monitoring_logger.removeHandler(self._monitoring_handler)
            self._monitoring_handler = None
            self._monitoring_logger = None
            self.logger.info(f"Finish log monitoring for logger: {self.logger.name}")
