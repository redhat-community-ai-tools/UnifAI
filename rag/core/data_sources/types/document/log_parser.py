"""Document-specific log parser for extracting document pipeline information."""
import re
from typing import Optional

from core.pipeline.domain.model import PipelineStatus
from core.monitoring.parsing.base import LogParser


class DocLogParser(LogParser):
    """
    Parser for document-specific log entries.
    
    This class extends the base LogParser with methods specific to document processing logs.
    """
    
    @staticmethod
    def extract_doc_id(log_line: str) -> Optional[str]:
        """
        Extract document ID from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The document ID or None if not found
        """
        # Try to find document ID in "Processing document" or similar log entries
        patterns = [
            r'Processing document: ([^/\s]+\.pdf|[^/\s]+\.docx|[^/\s]+\.txt)$',  # For direct filename references
            r'Processing document: .*?/([^/]+\.(pdf|docx|txt))$',  # For path-based references
            r'Processing document: .* \(ID: ([A-Za-z0-9_-]+)\)',  # For explicit ID references
            r'document ([^/\s]+\.(pdf|docx|txt)) in',  # For references in processing time logs
            r'Successfully processed document: ([^/\s]+\.(pdf|docx|txt))'  # For success logs
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_line)
            if match:
                return match.group(1)
        
        return None
    
    @staticmethod
    def extract_api_endpoint(log_line: str) -> Optional[str]:
        """
        Extract API endpoint from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The API endpoint or None if not found
        """
        # Pattern for httpx logs
        http_pattern = r'HTTP Request: (GET|POST|PUT|DELETE|PATCH) (http[s]?://[^\s"]+)'
        match = re.search(http_pattern, log_line)
        if match:
            return match.group(2)
        
        # Pattern for other API calls
        api_pattern = r'API request to ([^\s]+)'
        match = re.search(api_pattern, log_line)
        if match:
            return match.group(1)
            
        return None
    
    @staticmethod
    def extract_chunk_count(log_line: str) -> Optional[int]:
        """
        Extract chunk count from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The chunk count or None if not found
        """
        patterns = [
            r'Completed chunking with (\d+) total chunks generated'
        ]
        
        for pattern in patterns:
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
        patterns = [
            # r'Starting embedding generation for (\d+) chunks',
            # r'Storing (\d+) embeddings in',
            r'Stored (\d+) embeddings in'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_line)
            if match:
                return int(match.group(1))
        
        return None
    
    @staticmethod
    def extract_processing_status(log_line: str) -> Optional[PipelineStatus]:
        """
        Extract processing status from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The PipelineStatus or None if not found
        """
        if re.search(r'Starting to process', log_line):
            return PipelineStatus.ACTIVE
        elif re.search(r'Successfully processed document|Document processed successfully', log_line):
            return PipelineStatus.DONE
        elif re.search(r'Failed to process|Error processing document', log_line):
            return PipelineStatus.FAILED
        
        return None
