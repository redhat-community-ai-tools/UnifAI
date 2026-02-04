"""Handler for Slack 'channel_created' events."""
from typing import Dict, Any

from core.data_sources.types.slack.domain.event.port import SlackEventHandler
from core.data_sources.types.slack.domain.event.model import ChannelCreatedEvent
from core.data_sources.types.slack.domain.channel.model import SlackChannel
from core.data_sources.types.slack.domain.channel.repository import SlackChannelRepository
from shared.logger import logger


class ChannelCreatedEventHandler(SlackEventHandler):
    """
    Processes Slack 'channel_created' event to persist the channel.
    
    This handler receives webhook events when a new Slack channel is created
    and persists the channel information to the database.
    """
    
    event_type = "channel_created"
    
    def __init__(self, channel_repo: SlackChannelRepository, project_id: str):
        """
        Initialize the handler with injected dependencies.
        
        Args:
            channel_repo: Repository for Slack channel persistence
            project_id: Project ID to associate with channels
        """
        self._channel_repo = channel_repo
        self._project_id = project_id
    
    def handle(self, payload: Dict[str, Any]) -> None:
        """
        Process the channel_created event payload.
        
        Args:
            payload: Raw Slack webhook payload
        """
        try:
            typed = ChannelCreatedEvent.from_payload(payload)
            
            if typed.type != self.event_type:
                logger.debug(f"Ignoring event type '{typed.type}' in ChannelCreatedEventHandler")
                return
            
            if not typed.channel_id:
                logger.warning(f"Missing channel id for '{self.event_type}' event")
                return

            channel_info = typed.channel_raw
            if not channel_info:
                logger.warning(f"No channel payload found for {self.event_type}")
                return

            # Create domain model from Slack API response
            channel = SlackChannel.from_slack_api(channel_info, self._project_id)
            
            # Override last_updated with event timestamp if available
            if typed.event_ts:
                channel = SlackChannel(
                    channel_id=channel.channel_id,
                    channel_name=channel.channel_name,
                    project_id=channel.project_id,
                    channel_type=channel.channel_type,
                    is_private=channel.is_private,
                    is_app_member=channel.is_app_member,
                    last_updated=float(typed.event_ts),
                )

            created = self._channel_repo.save(channel)
            if created:
                logger.info(f"Cached new channel from {self.event_type}: {typed.channel_id}")
            else:
                logger.error(f"Failed to cache new channel from {self.event_type}: {typed.channel_id}")
                
        except Exception as e:
            logger.error(f"Error handling {self.event_type}: {e}", exc_info=True)
