"""SlackChannel domain model."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any
import time


class ChannelType(str, Enum):
    """Slack channel visibility type."""
    PRIVATE = "Private"
    PUBLIC = "Public"


@dataclass
class SlackChannel:
    """Domain model for a Slack channel."""
    channel_id: str
    channel_name: str
    project_id: str
    channel_type: ChannelType
    is_private: bool
    is_app_member: bool
    last_updated: float

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SlackChannel":
        """Create a SlackChannel instance from a dictionary."""
        channel_type_raw = data.get("type", "Public")
        channel_type = (
            ChannelType(channel_type_raw)
            if channel_type_raw in [t.value for t in ChannelType]
            else ChannelType.PUBLIC
        )
        return cls(
            channel_id=data.get("channel_id", ""),
            channel_name=data.get("channel_name", ""),
            project_id=data.get("project_id", ""),
            channel_type=channel_type,
            is_private=data.get("is_private", False),
            is_app_member=data.get("is_app_member", False),
            last_updated=data.get("last_updated", 0.0),
        )

    @classmethod
    def from_slack_api(cls, channel: Dict[str, Any], project_id: str) -> "SlackChannel":
        """Create a SlackChannel from Slack API response."""
        is_private = channel.get("is_private", False)
        return cls(
            channel_id=channel.get("id", ""),
            channel_name=channel.get("name", ""),
            project_id=project_id,
            channel_type=ChannelType.PRIVATE if is_private else ChannelType.PUBLIC,
            is_private=is_private,
            is_app_member=bool(channel.get("is_member", False)),
            last_updated=time.time(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert the SlackChannel instance to a dictionary."""
        return {
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "project_id": self.project_id,
            "type": self.channel_type.value,
            "is_private": self.is_private,
            "is_app_member": self.is_app_member,
            "last_updated": self.last_updated,
        }

