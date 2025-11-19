import re
from datetime import datetime
from typing import Optional, Tuple
from config.constants import PipelineStatus

class LogParser:
    """
    Utility class for parsing log lines and extracting relevant information.
    
    This class provides methods to extract statistics, status updates, and other
    useful data from log entries.
    """
    
    @staticmethod
    def parse_log_line(log_line: str) -> Tuple[datetime, str, str, str]:
        """
        Parse a log line into its components.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            Tuple containing (timestamp, module, log_level, message)
        """
        # Example log format: 2025-05-04 03:19:30,185 - data_pipeline - INFO - Making API request to Slack endpoint: auth.test
        pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) - (\w+) - (\w+) - (.*)'
        match = re.match(pattern, log_line)
        
        if match:
            timestamp_str, module, level, message = match.groups()
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S,%f")
            return timestamp, module, level, message
        
        # Fallback for logs that don't match the expected pattern
        return datetime.now(), "unknown", "INFO", log_line
    
    @staticmethod
    def extract_chunk_count(log_line: str) -> Optional[int]:
        """
        Extract chunk count from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The chunk count or None if not found
        """
        pattern = r'Generated (\d+) chunks'
        match = re.search(pattern, log_line)
        if match:
            return int(match.group(1))
        return None
    
    @staticmethod
    def extract_embedding_count(log_line: str) -> Optional[int]:
        """
        Extract embedding count from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The embedding count or None if not found
        """
        # pattern = r'Starting embedding generation for (\d+) chunks'
        # match = re.search(pattern, log_line)
        # if match:
        #     return int(match.group(1))
        
        pattern = r'Stored (\d+) embeddings'
        match = re.search(pattern, log_line)
        if match:
            return int(match.group(1))
            
        return None
    
    @staticmethod
    def extract_pipeline_status(log_line: str) -> Optional[PipelineStatus]:
        """
        Extract pipeline status from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The pipeline status or None if not found
        """
        # Examples to detect completion
        if "Stored" in log_line and "embeddings" in log_line:
            return PipelineStatus.DONE
        
        # Currently each pipeline already turned into 'ACTIVE' in the registeration procedure
        # Examples to detect active state
        # if "Making API request" in log_line or "Starting" in log_line:
        #     return PipelineStatus.ACTIVE
        
        # Examples to detect errors
        if "ERROR" in log_line or "Failed" in log_line:
            return PipelineStatus.FAILED
            
        return None