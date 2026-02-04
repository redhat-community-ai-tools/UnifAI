"""MongoDB adapter for SlackChannelRepository port."""
from typing import Optional, List, Dict, Any

from pymongo.collection import Collection

from core.data_sources.types.slack.domain.channel.model import SlackChannel
from core.data_sources.types.slack.domain.channel.repository import SlackChannelRepository
from core.pagination.domain.model import PaginatedResult
from infrastructure.mongo.pagination_builder import PaginatedQueryBuilder
from shared.logger import logger


class MongoSlackChannelRepository(SlackChannelRepository):
    """MongoDB implementation of the SlackChannelRepository port."""

    # Mapping from API types to internal types
    _TYPE_MAP = {
        "private_channel": "Private",
        "public_channel": "Public",
    }

    def __init__(self, collection: Collection):
        self._col = collection

    def find_by_channel_id(self, channel_id: str) -> Optional[SlackChannel]:
        """Find a channel by its ID."""
        try:
            doc = self._col.find_one({"channel_id": channel_id})
            return SlackChannel.from_dict(doc) if doc else None
        except Exception as e:
            logger.error(f"Error finding channel {channel_id}: {e}")
            return None

    def find_paginated(
        self,
        project_id: str,
        types: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """
        Get channels with pagination using the builder.
        
        Uses PaginatedQueryBuilder for consistent pagination logic.
        """
        builder = (PaginatedQueryBuilder(self._col)
            .with_filter({"project_id": project_id})
            .with_search(search, field="channel_name")
            .with_sort("channel_name", desc=False)  # Alphabetical
            .paginate(cursor, limit))
        
        if types:
            type_list = [self._TYPE_MAP.get(t.strip(), t.strip()) 
                        for t in types.split(",")]
            builder.with_filter({"type": {"$in": type_list}})
        
        return builder.documents()

    def exists_for_project(self, project_id: str) -> bool:
        """Check if there are any channels for the project."""
        return self._col.count_documents({"project_id": project_id}) > 0

    def save(self, channel: SlackChannel) -> bool:
        """Save a channel."""
        try:
            self._col.insert_one(channel.to_dict())
            return True
        except Exception as e:
            logger.error(f"Error inserting channel {channel.channel_id}: {e}")
            return False

    def save_many(self, channels: List[SlackChannel]) -> None:
        """Save multiple channels in batch."""
        if channels:
            docs = [ch.to_dict() for ch in channels]
            self._col.insert_many(docs)
            logger.info(f"Cached {len(channels)} channels to MongoDB")

    def update_membership(self, channel_id: str, is_member: bool, timestamp: float) -> bool:
        """Update membership flag."""
        try:
            result = self._col.update_one(
                {"channel_id": channel_id},
                {"$set": {"is_app_member": is_member, "last_updated": timestamp}},
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating membership for channel {channel_id}: {e}")
            return False

    def delete_by_project(self, project_id: str) -> int:
        """Delete all channels for a project."""
        result = self._col.delete_many({"project_id": project_id})
        logger.info(f"Cleared {result.deleted_count} existing channels for project {project_id}")
        return result.deleted_count
