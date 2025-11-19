from typing import Optional, Dict, List, Any
from pymongo.collection import Collection
import time
from shared.logger import logger


class SlackChannelsRepository:
    """Repository for managing Slack channel documents in MongoDB."""
    
    def __init__(self, col: Collection):
        self.col = col

    def clear_project_channels(self, project_id: str) -> None:
        """Clear all channels for a specific project to avoid duplicates."""
        result = self.col.delete_many({"project_id": project_id})
        logger.info(f"Cleared {result.deleted_count} existing channels for project {project_id}")

    def cache_channels(self, channels: List[Dict[str, Any]]) -> None:
        """Cache a batch of channels in MongoDB."""
        if channels:
            self.col.insert_many(channels)
            logger.info(f"Cached {len(channels)} channels to MongoDB")

    def get_channels_with_pagination(
        self, 
        project_id: str,
        types: Optional[str] = None, 
        cursor: Optional[str] = None, 
        limit: int = 50, 
        search_regex: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get channels from cache with pagination support.
        
        Args:
            project_id: Project ID to filter by
            types: Optional channel types to filter by ('private_channel', 'public_channel', or 'private_channel,public_channel')
            cursor: Optional cursor for pagination (skip count)
            limit: Number of channels to return (default: 50)
            search_regex: Optional regex pattern to search channel names
            
        Returns:
            Dictionary containing paginated channels data with pagination metadata
        """
        # Build query filter
        query_filter: Dict[str, Any] = {"project_id": project_id}
        
        if types:
            # Convert types to cache types for querying
            channel_types = [t.strip() for t in types.split(',')]
            cache_types = []
            for channel_type in channel_types:
                if channel_type == "private_channel":
                    cache_types.append("Private")
                elif channel_type == "public_channel":
                    cache_types.append("Public")
                else:
                    cache_types.append(channel_type)  # fallback
            query_filter['type'] = {"$in": cache_types}
        
        # Add regex search filter if provided
        if search_regex:
            try:
                # Use MongoDB regex with case-insensitive flag
                query_filter['channel_name'] = {"$regex": search_regex, "$options": "i"}
            except Exception as regex_error:
                logger.warning(f"Invalid regex pattern '{search_regex}': {str(regex_error)}. Ignoring regex filter.")
        
        # Get total count for pagination metadata
        total_count = self.col.count_documents(query_filter)
        
        # Calculate skip value from cursor
        skip = 0
        if cursor:
            try:
                skip = int(cursor)
            except ValueError:
                logger.warning(f"Invalid cursor value: {cursor}, using 0")
                skip = 0
        
        # Fetch channels from cache with pagination
        cached_channels = list(self.col.find(query_filter, {'_id': 0})
                             .skip(skip)
                             .limit(limit))
        
        # Calculate next cursor and hasMore
        next_cursor = None
        has_more = False
        
        if len(cached_channels) == limit and (skip + limit) < total_count:
            next_cursor = str(skip + limit)
            has_more = True
        
        search_info = f" with regex '{search_regex}'" if search_regex else ""
        logger.info(f"Retrieved {len(cached_channels)} Slack channels from cache{search_info} (page {skip}-{skip+limit} of {total_count})")
        
        return {
            'channels': cached_channels,
            'nextCursor': next_cursor,
            'hasMore': has_more,
            'total': total_count,
        }

    def has_cached_channels(self, project_id: str) -> bool:
        """Check if there are any cached channels for the project."""
        return self.col.count_documents({"project_id": project_id}) > 0

    def create_channel_document(self, channel: Dict[str, Any], project_id: str) -> Dict[str, Any]:
        """Create a channel document with standard fields, including membership info if available."""
        return {
            'channel_id': channel.get('id'),
            'channel_name': channel.get('name'),
            'type': 'Private' if channel.get('is_private', False) else 'Public',
            'is_private': channel.get('is_private', False),
            'project_id': project_id,
            # Prefer provided membership, else fall back to Slack payload if present
            'is_app_member': bool(channel.get('is_member', False)),
            'last_updated': time.time()
        }

    def find_by_channel_id(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """Find a single channel document by channel_id."""
        try:
            return self.col.find_one({"channel_id": channel_id})
        except Exception as e:
            logger.error(f"Error finding channel {channel_id}: {e}")
            return None

    def update_membership(self, channel_id: str, is_member: bool, timestamp: float) -> bool:
        """Update membership flag and timestamp on a channel document by channel_id."""
        try:
            result = self.col.update_one(
                {"channel_id": channel_id},
                {"$set": {"is_app_member": is_member, "last_updated": timestamp}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating membership for channel {channel_id}: {e}")
            return False

    def insert_channel(self, channel_doc: Dict[str, Any]) -> bool:
        """Insert a new channel document."""
        try:
            self.col.insert_one(channel_doc)
            return True
        except Exception as e:
            logger.error(f"Error inserting channel {channel_doc.get('channel_id', 'unknown')}: {e}")
            return False