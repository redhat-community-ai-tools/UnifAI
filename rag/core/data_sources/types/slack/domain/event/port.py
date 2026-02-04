"""
Port (interface) for Slack event handlers.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class SlackEventHandler(ABC):
    """
    Abstract base class for Slack event handlers.
    
    Each handler must declare a unique event_type and implement handle().
    """
    
    # Slack event type this handler is responsible for (e.g., "channel_created")
    event_type: str
    
    @abstractmethod
    def handle(self, payload: Dict[str, Any]) -> None:
        """Process the Slack payload for the supported event type."""
        ...

