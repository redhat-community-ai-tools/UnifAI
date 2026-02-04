"""Slack-specific log parser for extracting Slack pipeline information."""
import re
from typing import Optional

from core.monitoring.parsing.base import LogParser


class SlackLogParser(LogParser):
    """
    Parser for Slack-specific log entries.
    
    This class extends the base LogParser with methods specific to Slack processing logs.
    """
    
    @staticmethod
    def extract_slack_channel_id(log_line: str) -> Optional[str]:
        """
        Extract Slack channel ID from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The channel ID or None if not found
        """
        pattern = r'ID: ([A-Z0-9]+)'
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
        pattern = r'API request to Slack endpoint: ([\w\.]+)'
        match = re.search(pattern, log_line)
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def extract_message_count(log_line: str) -> Optional[int]:
        """
        Extract message count from a log line if present.
        
        Args:
            log_line: A string containing a log entry
            
        Returns:
            The message count or None if not found
        """
        pattern = r'Retrieved (\d+) messages'
        match = re.search(pattern, log_line)
        if match:
            return int(match.group(1))
        return None
