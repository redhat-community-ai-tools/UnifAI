"""
A2A Response Handlers Package.

Handlers auto-register via BaseHandler.__init_subclass__.
Handles SUCCESS response types. Errors handled directly by client.

Usage:
    from elements.providers.a2a_client.handlers import BaseHandler
    
    result = BaseHandler.handle(sdk_object)
"""

from .base_handler import BaseHandler

# Import handlers to trigger auto-registration
from .handlers import (
    TaskHandler,
    MessageHandler,
    StatusEventHandler,
    ArtifactEventHandler,
)

__all__ = [
    "BaseHandler",
    "TaskHandler",
    "MessageHandler",
    "StatusEventHandler",
    "ArtifactEventHandler",
]
