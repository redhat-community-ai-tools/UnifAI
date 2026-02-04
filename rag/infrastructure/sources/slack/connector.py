"""Slack connector - infrastructure adapter for Slack API."""
import requests
import time
from typing import Dict, List, Optional, Any, Tuple
from shared.logger import logger
from infrastructure.sources.slack.config import SlackConfigManager
from core.connector.domain.base import DataConnector
from core.data_sources.types.slack.domain.channel.model import SlackChannel
from core.data_sources.types.slack.domain.channel.repository import SlackChannelRepository
from infrastructure.sources.slack.thread_retriever import SlackThreadRetriever
from infrastructure.sources.slack.thread_retriever_worker import ThreadRetrieverWorker


class SlackConnector(DataConnector):
    """
    Connector for retrieving data from Slack.
    
    Handles authentication, rate limiting, and pagination for Slack API calls.
    """
    
    def __init__(
        self,
        config_manager: SlackConfigManager,
        channel_repo: SlackChannelRepository,
        project_id: Optional[str] = None,
    ):
        """
        Initialize the Slack connector.
        
        Args:
            config_manager: Configuration manager for Slack
            channel_repo: Repository for Slack channel persistence
            project_id: Optional project ID to use, defaults to the default project
        """
        super().__init__(config_manager)
        self.base_url = "https://slack.com/api/"
        self._available_apis = [
            "users.profile.get",
            "users.info",
            "conversations.history",
            "conversations.list",
            "conversations.replies",
            "files.info",
        ]
        
        # Set the project ID
        self._project_id = project_id or config_manager.get_default_project()
        if not self._project_id:
            raise ValueError("No project ID provided and no default project set")
        
        # Injected repository
        self._channel_repo = channel_repo
        
        # Get tokens for the project
        try:
            tokens = config_manager.get_project_tokens(self._project_id)
            self._user_token = tokens.get('user_token')
            self._bot_token = tokens.get('bot_token')
            
            if not self._bot_token:
                raise ValueError(f"Bot token not configured for project {self._project_id}")
                
        except KeyError as e:
            raise ValueError(f"Project tokens not found: {str(e)}")
    
    def authenticate(self) -> bool:
        """
        Authenticate with Slack API using configured tokens.
        
        Returns:
            True if authentication succeeds, False otherwise
        """
        try:
            # Test authentication by calling the auth.test endpoint
            response = self._make_api_request("auth.test")
            
            if response.get('ok'):
                logger.info(f"Successfully authenticated with Slack as {response.get('user')}")
                return True
            else:
                logger.error(f"Slack authentication failed: {response.get('error')}")
                return False
                
        except Exception as e:
            logger.error(f"Slack authentication error: {str(e)}")
            return False
    
    def test_connection(self) -> bool:
        """
        Test connection to Slack API.
        
        Returns:
            True if connection is successful, False otherwise
        """
        return self.authenticate()
    
    def _make_api_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None, 
                          method: str = "GET", use_user_token: bool = False) -> Dict[str, Any]:
        """
        Make a request to the Slack API with rate limiting handling.
        
        Args:
            endpoint: The API endpoint (without base URL)
            params: Optional parameters to send with the request
            method: HTTP method to use (GET or POST)
            use_user_token: Whether to use the user token instead of the bot token
            
        Returns:
            The response from the API as a dictionary
            
        Raises:
            Exception: If the request fails after all retries
        """
        url = f"{self.base_url}{endpoint}"
        token = self._user_token if use_user_token else self._bot_token
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json; charset=utf-8"
        }
        
        # Track retry attempts
        max_retries = 3
        retry_count = 0
        last_error = None
        
        while retry_count <= max_retries:
            try:
                logger.info(f"Making API request to Slack endpoint: {endpoint} (attempt {retry_count + 1}/{max_retries + 1})")
                
                if method.upper() == "GET":
                    response = requests.get(url, headers=headers, params=params, timeout=30)
                else:  # POST
                    response = requests.post(url, headers=headers, json=params, timeout=30)
                
                response_data = response.json()
                
                # Check for rate limiting
                if not response_data.get('ok') and response_data.get('error') == 'ratelimited':
                    retry_after = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited by Slack API. Retrying in {retry_after} seconds.")
                    time.sleep(retry_after)
                    retry_count += 1
                    continue
                
                # Check for other API errors
                if not response_data.get('ok'):
                    error_msg = response_data.get('error', 'unknown_error')
                    logger.error(f"Slack API error for {endpoint}: {error_msg}")
                    
                    # Some errors are worth retrying, others are not
                    retryable_errors = ['ratelimited', 'timeout', 'internal_error', 'fatal_error']
                    if error_msg in retryable_errors and retry_count < max_retries:
                        wait_time = min(2 ** retry_count, 60)  # Cap at 60 seconds
                        logger.info(f"Retryable error {error_msg}, waiting {wait_time} seconds before retry...")
                        time.sleep(wait_time)
                        retry_count += 1
                        continue
                    else:
                        # Non-retryable error or max retries reached
                        raise Exception(f"Slack API error: {error_msg}")
                
                logger.info(f"Slack API request to {endpoint} successful")
                return response_data
                
            except requests.exceptions.RequestException as e:
                last_error = e
                logger.error(f"Network error making request to Slack API {endpoint}: {str(e)}")
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 60)  # Exponential backoff, capped at 60 seconds
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    break
            except Exception as e:
                last_error = e
                logger.error(f"Unexpected error making request to Slack API {endpoint}: {str(e)}")
                if retry_count < max_retries:
                    wait_time = min(2 ** retry_count, 30)  # Shorter backoff for unexpected errors
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                    retry_count += 1
                else:
                    break
        
        # All retries exhausted
        error_msg = f"Maximum retries ({max_retries + 1}) exceeded when calling Slack API endpoint '{endpoint}'"
        if last_error:
            error_msg += f". Last error: {str(last_error)}"
        
        logger.error(error_msg)
        raise Exception(error_msg)
    
    def fetch_available_slack_channels(self) -> List[Dict[str, str]]:
        """
        Fetch all available Slack channels (both public and private) and cache them in MongoDB.
        This function fetches all channels without API call limits and stores them in the database.
        
        Returns:
            List of dictionaries containing channel_id, channel_name, and type
        """
        channels: List[SlackChannel] = []
        cursor = None
        api_call_count = 0
        
        # Clear existing channels for this project to avoid duplicates
        self._channel_repo.delete_by_project(self._project_id)
        
        # Fetch all channels (both public and private) until there's no next_cursor
        while True:
            params: Dict[str, Any] = {"limit": 1000, "types": "public_channel,private_channel"}
            if cursor:
                params['cursor'] = cursor
            
            response = self._make_api_request("conversations.list", params)
            api_call_count += 1
            
            if not response.get('ok'):
                logger.error(f"Failed to get channels: {response.get('error')}")
                break
            
            # Process channels from current page
            batch_channels: List[SlackChannel] = []
            for channel in response.get('channels', []):
                channel_model = SlackChannel.from_slack_api(channel, self._project_id)
                channels.append(channel_model)
                batch_channels.append(channel_model)
            
            # Cache batch to MongoDB
            self._channel_repo.save_many(batch_channels)
            
            # Check if there are more pages
            response_metadata = response.get('response_metadata', {})
            cursor = response_metadata.get('next_cursor')
            
            # If no next_cursor or it's empty, we've reached the end
            if not cursor:
                break
        
        logger.info(f"Retrieved and cached {len(channels)} Slack channels from {api_call_count} API calls")
        return [ch.to_dict() for ch in channels]
    
    def get_available_slack_channels_from_cache(self, types: Optional[str] = None, cursor: Optional[str] = None, limit: int = 50, search_regex: Optional[str] = None) -> Dict[str, Any]:
        """
        Get available Slack channels from cache (MongoDB) with pagination support.
        This function reads from the cached channels without making API calls.
        
        Args:
            types: Optional channel types to filter by ('private_channel', 'public_channel', or 'private_channel,public_channel')
            cursor: Optional cursor for pagination (skip count)
            limit: Number of channels to return (default: 50)
            search_regex: Optional regex pattern to search channel names
            
        Returns:
            Dictionary containing paginated channels data with pagination metadata
        """
        try:
            # Get channels from repository with pagination
            result = self._channel_repo.find_paginated(
                project_id=self._project_id,
                types=types,
                cursor=cursor,
                limit=limit,
                search=search_regex,
            )
            # Convert PaginatedResult to dict for backward compatibility
            return result.to_dict("channels")
            
        except Exception as e:
            logger.error(f"Error retrieving channels from cache: {str(e)}")
            if search_regex:
                # For regex searches, return empty results instead of fallback
                logger.warning("Returning empty results for regex search")
                return {
                    'channels': [],
                    'nextCursor': None,
                    'hasMore': False,
                    'total': 0,
                }
            else:
                logger.warning("Falling back to API call with limited results")
                return self._fallback_with_pagination(types, cursor, limit)
    
    def _fallback_with_pagination(self, types: Optional[str] = None, cursor: Optional[str] = None, limit: int = 50) -> Dict[str, Any]:
        """
        Fallback method that fetches channels from API and formats them with pagination.
        
        Args:
            types: Optional channel types to filter by
            cursor: Optional cursor for pagination (skip count)
            limit: Number of channels to return
            
        Returns:
            Dictionary containing paginated channels data with pagination metadata
        """
        # Fallback to API call with limited results if cache fails
        fallback_channels = self._fallback_get_channels(types, max_api_calls=5)
        
        # Transform fallback response to paginated format
        skip = 0
        if cursor:
            try:
                skip = int(cursor)
            except ValueError:
                logger.warning(f"Invalid cursor value: {cursor}, using 0")
                skip = 0
        
        start_idx = skip
        end_idx = start_idx + limit
        paginated_channels = fallback_channels[start_idx:end_idx]
        
        return {
            'channels': paginated_channels,
            'nextCursor': str(end_idx) if end_idx < len(fallback_channels) else None,
            'hasMore': end_idx < len(fallback_channels),
            'total': len(fallback_channels),
        }
    
    def _fallback_get_channels(self, types: Optional[str] = None, max_api_calls: int = 5) -> List[Dict[str, str]]:
        """
        Fallback method to get channels directly from API with limited calls.
        Used when cache retrieval fails.
        
        Args:
            types: Optional channel types to filter by (e.g., 'private_channel', 'public_channel')
            max_api_calls: Maximum number of API calls to make
            
        Returns:
            List of dictionaries containing channel_id, channel_name, and is_private
        """
        channels: List[SlackChannel] = []
        cursor = None
        api_call_count = 0
        
        while api_call_count < max_api_calls:
            params: Dict[str, Any] = {"limit": 1000}
            if types:
                params['types'] = types
            if cursor:
                params['cursor'] = cursor
            
            response = self._make_api_request("conversations.list", params)
            api_call_count += 1
            
            if not response.get('ok'):
                logger.error(f"Failed to get channels: {response.get('error')}")
                break
            
            # Process channels from current page
            for channel in response.get('channels', []):
                channel_model = SlackChannel.from_slack_api(channel, self._project_id)
                channels.append(channel_model)
            
            # Check if there are more pages
            response_metadata = response.get('response_metadata', {})
            cursor = response_metadata.get('next_cursor')
            
            # If no next_cursor or it's empty, we've reached the end
            if not cursor:
                break
        
        logger.info(f"Retrieved {len(channels)} Slack channels from {api_call_count} fallback API calls")
        return [ch.to_dict() for ch in channels]
    
    def get_conversations_history(
        self,
        channel_id: str,
        limit: int = 1000,
        cursor: Optional[str] = None,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], List[List[Dict[str, Any]]]]:
        """
        Get conversation history for a Slack channel with pagination handling and concurrently fetches thread replies.
        
        Args:
            channel_id: The ID of the channel to fetch history for
            limit: Maximum number of messages to return per page
            cursor: Pagination cursor from a previous request
        
        Returns:
            List of message objects from the conversation history
        """
        all_messages = []
        current_cursor = cursor
        has_more = True
        page = 1

        thread_retriever = SlackThreadRetriever(self)
        thread_worker = ThreadRetrieverWorker(thread_retriever, oldest=oldest, latest=latest)
        
        while has_more:
            params = {
                'channel': channel_id,
                'limit': limit
            }
            if oldest:
                params['oldest'] = oldest
            if latest:
                params['latest'] = latest
            
            if current_cursor:
                params['cursor'] = current_cursor
            
            logger.info(f"Fetching conversation history (page {page}) for channel {channel_id}")
            response = self._make_api_request("conversations.history", params)
            
            if not response.get('ok'):
                logger.error(f"Failed to get conversation history: {response.get('error')}")
                break
                
            messages = response.get('messages', [])
            all_messages.extend(messages)
            logger.info(f"Retrieved {len(messages)} messages from channel {channel_id}")

            # Slack's conversations.history API only includes top-level messages in a channel, thread_replies aren't included in the response
            for msg in messages:
                # If the message is the parent of a thread, submit it to the thread worker queue
                if msg.get("thread_ts") == msg.get("ts"):
                    thread_worker.submit(channel_id, msg["ts"])
            
            # Check if there are more messages to fetch
            response_metadata = response.get('response_metadata', {})
            current_cursor = response_metadata.get('next_cursor')
            has_more = bool(current_cursor and response.get('has_more', False))
            page += 1
        
        logger.info(f"Retrieved a total of {len(all_messages)} messages from channel {channel_id}")
        
        thread_messages = thread_worker.gather_results()
        logger.info(f"Retrieved a total of {len(thread_messages)} threads from channel {channel_id}")

        return all_messages, thread_messages
    
    def get_user_info(self, user_id: Optional[str] = None, include_locale: bool = False) -> Dict[str, Any]:
        """
        Get information about a user using Slack's users.info API.
        
        Args:
            user_id: User ID to get info for. If None, gets info for the current authenticated user.
            include_locale: Whether to include locale information in the response.
            
        Returns:
            Dictionary containing user information
            
        Raises:
            Exception: If the API request fails
        """
        params: Dict[str, Any] = {}
        
        # If no user_id provided, get the current user from auth.test
        if not user_id:
            auth_response = self._make_api_request("auth.test", use_user_token=True)
            if auth_response.get('ok'):
                user_id = auth_response.get('user_id')
            else:
                raise Exception("Failed to get current user ID from auth.test")
        
        params['user'] = user_id
            
        if include_locale:
            params['include_locale'] = 'true'
        
        logger.info(f"Fetching user info for user_id: {user_id or 'current user'}")
        response = self._make_api_request("users.info", params, use_user_token=True)
        
        if not response.get('ok'):
            error_msg = f"Failed to get user info: {response.get('error')}"
            logger.error(error_msg)
            raise Exception(error_msg)
        
        user_info = response.get('user', {})
        logger.info(f"Successfully retrieved user info for user: {user_info.get('name', 'Unknown')}")
        
        return response
