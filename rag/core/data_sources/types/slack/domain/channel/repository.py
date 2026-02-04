"""Slack channel repository port (interface)."""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from core.data_sources.types.slack.domain.channel.model import SlackChannel
from core.pagination.domain.model import PaginatedResult


class SlackChannelRepository(ABC):
    """Port for SlackChannel persistence."""

    @abstractmethod
    def find_by_channel_id(self, channel_id: str) -> Optional[SlackChannel]:
        """Find a channel by its ID."""
        ...

    @abstractmethod
    def find_paginated(
        self,
        project_id: str,
        types: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 50,
        search: Optional[str] = None,
    ) -> PaginatedResult[Dict[str, Any]]:
        """
        Get channels with pagination support.
        
        Args:
            project_id: Project ID to filter by
            types: Optional channel types (comma-separated: "private_channel,public_channel")
            cursor: Optional cursor for pagination
            limit: Number of channels to return
            search: Optional search pattern for channel names
            
        Returns:
            PaginatedResult containing channel documents
        """
        ...

    @abstractmethod
    def exists_for_project(self, project_id: str) -> bool:
        """Check if there are any channels for the project."""
        ...

    @abstractmethod
    def save(self, channel: SlackChannel) -> bool:
        """Save a channel. Returns True if successful."""
        ...

    @abstractmethod
    def save_many(self, channels: List[SlackChannel]) -> None:
        """Save multiple channels in batch."""
        ...

    @abstractmethod
    def update_membership(self, channel_id: str, is_member: bool, timestamp: float) -> bool:
        """Update membership flag. Returns True if updated."""
        ...

    @abstractmethod
    def delete_by_project(self, project_id: str) -> int:
        """Delete all channels for a project. Returns count deleted."""
        ...
