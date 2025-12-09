"""
BaseHandler - Abstract base for A2A response type handlers.

Handlers auto-register via __init_subclass__.
No separate registry needed.
"""

from abc import ABC, abstractmethod
from typing import Any, Type, Set, ClassVar, Dict, Optional

from elements.providers.a2a_client.result import A2AResult


class BaseHandler(ABC):
    """
    Base handler for A2A SDK response types.
    
    Handlers auto-register when defined via __init_subclass__.
    Use BaseHandler.handle() to dispatch to the right handler.
    
    Required class attributes:
        handled_types: Set of SDK types this handler processes
    """

    # Class-level registry: SDK type → handler class
    _registry: ClassVar[Dict[Type, Type["BaseHandler"]]] = {}

    # Required attribute
    handled_types: ClassVar[Set[Type]]

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Auto-register handler when class is defined."""
        super().__init_subclass__(**kwargs)

        # Skip abstract classes
        if ABC in cls.__bases__:
            return

        # Validate
        if not hasattr(cls, "handled_types") or not cls.handled_types:
            raise TypeError(f"{cls.__name__} must define non-empty 'handled_types'")

        # Auto-register for each handled type
        for sdk_type in cls.handled_types:
            BaseHandler._registry[sdk_type] = cls

    @abstractmethod
    def convert(self, obj: Any, is_streaming: bool = False) -> A2AResult:
        """
        Convert SDK object to A2AResult.
        
        Args:
            obj: SDK response object
            is_streaming: Whether from streaming endpoint
            
        Returns:
            A2AResult wrapping the object
        """
        pass

    @classmethod
    def handle(cls, obj: Any, is_streaming: bool = False) -> Optional[A2AResult]:
        """
        Find handler and convert object to A2AResult.
        
        Args:
            obj: SDK response object
            is_streaming: Whether from streaming endpoint
            
        Returns:
            A2AResult if handler found, None otherwise
        """
        # Direct type lookup
        handler_cls = cls._registry.get(type(obj))
        if handler_cls:
            return handler_cls().convert(obj, is_streaming=is_streaming)

        # Fallback: isinstance check for subclasses
        for sdk_type, handler_cls in cls._registry.items():
            if isinstance(obj, sdk_type):
                return handler_cls().convert(obj, is_streaming=is_streaming)

        return None

    @classmethod
    def get_registered_types(cls) -> list:
        """List all registered SDK types."""
        return list(cls._registry.keys())

    @classmethod
    def get_handler_for(cls, sdk_type: Type) -> Optional[Type["BaseHandler"]]:
        """Get handler class for a specific SDK type."""
        return cls._registry.get(sdk_type)
