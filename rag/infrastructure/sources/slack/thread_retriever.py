"""Slack thread retriever - infrastructure helper for SlackConnector."""
from typing import Dict, List, Any, Optional
from shared.logger import logger


class SlackThreadRetriever:
    """
    Helper class for retrieving threaded conversations from Slack.
    
    This class extends the functionality of SlackConnector to specifically
    handle threaded message retrieval.
    """
    
    def __init__(self, slack_connector):
        """
        Initialize the thread retriever.
        
        Args:
            slack_connector: Instance of SlackConnector to use for API calls
        """
        self._connector = slack_connector
    
    def get_thread_replies(
        self,
        channel_id: str,
        thread_ts: str,
        thread_number: int,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get all replies in a thread.
        
        Args:
            channel_id: The channel ID where the thread is located
            thread_ts: The timestamp of the parent message
            thread_number: The thread number (for logging)
            oldest: Optional oldest timestamp to fetch from
            latest: Optional latest timestamp to fetch to
            
        Returns:
            List of message objects from the thread
        """
        params = {
            'channel': channel_id,
            'ts': thread_ts,
            'limit': 1000  # Maximum allowed by Slack API
        }
        if oldest:
            params['oldest'] = oldest
        if latest:
            params['latest'] = latest
        
        response = self._connector._make_api_request("conversations.replies", params)
        
        if not response.get('ok'):
            logger.error(f"Failed to get thread replies: {response.get('error')}")
            return []
        
        # The first message is the parent message, which we might already have
        messages = response.get('messages', [])
        logger.info(f"Fetching conversation replies (thread {thread_number}) for channel {channel_id}")
        logger.info(f"Retrieved {len(messages)} messages from thread {thread_number}")
        
        return messages
