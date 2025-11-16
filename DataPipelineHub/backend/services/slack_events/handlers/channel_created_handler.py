"""
Handler for Slack 'channel_created' events.
"""

from typing import Dict, Any
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from shared.logger import logger
from ..event_handler import SlackEventHandler
from ..slack_event_models import ChannelCreatedEvent
import time


class ChannelCreatedEventHandler(SlackEventHandler):
    """
    Processes Slack 'channel_created' event to persist the channel in Mongo.
    """
    
    event_type = "channel_created"
    
    def __init__(self):
        storage = get_mongo_storage()
        self._repo = storage.slack_channels
    
    def handle(self, payload: Dict[str, Any]) -> None:
        try:
            # Parse this handler's typed event directly
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

            event_time = float(typed.event_ts) if typed.event_ts else time.time()

            # todo: get the project id from a general config across all code components 
            channel_doc = self._repo.create_channel_document(
                channel_info,
                "example-project",
            )
            channel_doc["last_updated"] = event_time

            created = self._repo.insert_channel(channel_doc)
            if created:
                logger.info(f"Cached new channel from {self.event_type}: {typed.channel_id}")
            else:
                logger.error(f"Failed to cache new channel from {self.event_type}: {typed.channel_id}")
        except Exception as e:
            logger.error(f"Error handling {self.event_type}: {e}", exc_info=True)


