import re
from typing import Dict, List, Any

from core.processing.domain.base import DataProcessor
from shared.logger import logger

class SlackProcessor(DataProcessor):
    """
    Processor for Slack message data.
    
    Handles the transformation of raw Slack message data into a clean,
    normalized format suitable for embedding in a vector database.
    """
    
    def __init__(self):
        """Initialize the Slack processor."""
        super().__init__()
        
    def process(self, data: List[Dict[str, Any]], channel_name: str) -> List[Dict[str, Any]]:
        """
        Process Slack message data.
        
        Args:
            data: List of raw Slack messages from the conversations.history API
            channel_name: Name of the Slack channel the messages are from
            
        Returns:
            List of processed Slack messages with normalized content
        """
        logger.info(f"Starting to process {len(data)} Slack messages from channel: {channel_name}")
        
        self._data = data
        self._processed_data = []
        
        for message in data:
            # Skip messages without required fields
            if not all(key in message for key in ["ts", "user", "text"]):
                logger.debug(f"Skipping message due to missing required fields: {message}")
                continue
                
            # Create processed message with required fields
            processed_message = {
                "time_stamp": message["ts"],
                "user": message["user"],
                "text": self.clean_content(message["text"]),
                "metadata": {
                    "channel_name": channel_name
                }
            }
            
            # Add thread_ts if exists (for threaded messages)
            if "thread_ts" in message:
                processed_message["metadata"]["thread_ts"] = message["thread_ts"]
                
            self._processed_data.append(processed_message)
            
        logger.info(f"Finished processing Slack messages. Processed {len(self._processed_data)} out of {len(data)} messages")
        return self._processed_data
    
    def clean_content(self, content: str) -> str:
        """
        Clean and normalize Slack message text.
        
        Args:
            content: Raw message text from Slack API
            
        Returns:
            Cleaned and normalized text
        """
        if not content:
            return ""
            
        # Pass content through formatting handlers
        cleaned_text = self._handle_user_mentions(content)
        cleaned_text = self._handle_channel_mentions(cleaned_text)
        cleaned_text = self._handle_special_formatting(cleaned_text)
        cleaned_text = self._handle_urls(cleaned_text)
        
        return cleaned_text.strip()
    
    def _handle_user_mentions(self, text: str) -> str:
        """
        Handle Slack user mention formatting (<@USER_ID>).
        
        In the future, this could replace user IDs with actual names.
        
        Args:
            text: Text containing user mentions
            
        Returns:
            Text with standardized user mentions
        """
        # For now, we're keeping the user ID but normalizing the format
        # Future enhancement: Replace with actual user names via the Slack Users API
        return re.sub(r'<@([A-Z0-9]+)>', r'@\1', text)
    
    def _handle_channel_mentions(self, text: str) -> str:
        """
        Handle Slack channel mention formatting (<#CHANNEL_ID|channel_name>).
        
        Args:
            text: Text containing channel mentions
            
        Returns:
            Text with standardized channel mentions
        """
        import re
        return re.sub(r'<#([A-Z0-9]+)\|([^>]+)>', r'#\2', text)
    
    def _handle_special_formatting(self, text: str) -> str:
        """
        Handle Slack's special text formatting (bold, italic, code blocks).
        
        Args:
            text: Text with Slack formatting
            
        Returns:
            Text with normalized formatting
        """
        import re
        
        # Handle code blocks
        text = re.sub(r'```(.*?)```', r'\1', text, flags=re.DOTALL)
        text = re.sub(r'`(.*?)`', r'\1', text)
        
        # Handle bold and italic
        text = re.sub(r'\*(.*?)\*', r'\1', text)
        text = re.sub(r'_(.*?)_', r'\1', text)
        
        # Handle strikethrough
        text = re.sub(r'~(.*?)~', r'\1', text)
        
        return text
    
    def _handle_urls(self, text: str) -> str:
        """
        Handle Slack URL formatting (<https://example.com|link text>).
        
        Args:
            text: Text containing formatted URLs
            
        Returns:
            Text with standardized URLs
        """
        import re
        
        # Replace <URL|text> with text
        text = re.sub(r'<(https?://[^|]+)\|([^>]+)>', r'\2', text)
        
        # Replace <URL> with URL
        text = re.sub(r'<(https?://[^>]+)>', r'\1', text)
        
        return text
        
    def batch_process(self, data_batches: List[Dict[str, Any]], channel_name: str) -> List[Dict[str, Any]]:
        """
        Process batches in parallel using threading or multiprocessing.
        
        Useful for processing large datasets or messages from multiple API calls.
        
        Args:
            data_batches: List of message batches
            channel_name: Name of the Slack channel
            
        Returns:
            Combined list of all processed messages"""
        from concurrent.futures import ThreadPoolExecutor
        
        logger.info(f"Starting parallel batch processing of {len(data_batches)} batches")
        all_processed = []
        
        with ThreadPoolExecutor() as executor:
            results = list(executor.map(
                lambda batch: self.process(batch, channel_name), 
                data_batches
            ))
            
        for result in results:
            all_processed.extend(result)

        logger.info(f"Completed batch processing. Total processed messages: {len(all_processed)}")            
        return all_processed

