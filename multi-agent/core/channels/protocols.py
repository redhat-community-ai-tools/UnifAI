"""
Channel protocols - abstractions for bidirectional session communication.

SessionChannel: ABC for session-scoped channels (emit, close, future: input)
StreamEmitter: ABC for emitting data during graph execution
"""
from abc import ABC, abstractmethod
from typing import Any


class StreamEmitter(ABC):
    """
    Abstract base class for emitting data during graph execution.
    Engine-specific implementations (e.g., LangGraphEmitter).
    """
    
    @abstractmethod
    def emit(self, data: Any) -> None:
        """Emit a chunk of data."""
        ...
    
    @abstractmethod
    def is_active(self) -> bool:
        """Check if emission is possible."""
        ...


class SessionChannel(ABC):
    """
    Abstract base class for session-scoped communication channels.
    
    Current: Output only (emit)
    Future: Add request_input() for HITL
    """
    
    @property
    @abstractmethod
    def session_id(self) -> str:
        """The session this channel belongs to."""
        ...
    
    @abstractmethod
    def emit(self, data: Any) -> None:
        """Emit data to the channel."""
        ...
    
    @abstractmethod
    def is_active(self) -> bool:
        """Check if channel is active."""
        ...
    
    @abstractmethod
    def close(self) -> None:
        """Close the channel."""
        ...
    
    def supports_input(self) -> bool:
        """
        Check if this channel supports receiving input (HITL).
        Default: False. Override in RedisSessionChannel.
        """
        return False

