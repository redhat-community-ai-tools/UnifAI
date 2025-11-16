"""
Simple service to dispatch Slack events to their handlers.
"""

from typing import Dict, Any, Callable, Type
from .event_handler import SlackEventHandler


class SlackEventService:
    """
    Maintains a registry of handler factories and dispatches payloads by event type.
    """
    
    def __init__(self):
        # Maps event_type -> factory that returns a SlackEventHandler
        self._event_factories: Dict[str, Callable[[], SlackEventHandler]] = {}
    
    def register_factory(self, event_type: str, factory: Callable[[], SlackEventHandler]) -> None:
        self._event_factories[event_type] = factory
    
    def register_class(self, handler_cls: Type[SlackEventHandler]) -> None:
        """Convenience to register a handler class directly."""
        self.register_factory(handler_cls.event_type, handler_cls)  # type: ignore[arg-type]
    
    def dispatch(self, payload: Dict[str, Any]) -> bool:
        """
        Dispatch payload to the matching handler by event.type.
        
        Returns True if a handler was found and executed, False otherwise.
        """
        event_data = payload.get("event", {}) or {}
        event_type = event_data.get("type")
        if not event_type:
            return False
        
        event_factory = self._event_factories.get(event_type)
        if not event_factory:
            return False
        
        event_handler = event_factory()
        event_handler.handle(payload)
        return True


