"""
Local session channel for Flask direct mode.
Wraps a StreamEmitter for same-process execution.
"""
from typing import Any, Optional
from core.channels import SessionChannel, StreamEmitter


class LocalSessionChannel(SessionChannel):
    """
    Session channel for same-process execution (Flask direct mode).
    Uses a StreamEmitter (e.g., LangGraphEmitter) for output.
    
    Does not support HITL (supports_input returns False).
    """
    
    def __init__(self, session_id: str, emitter: Optional[StreamEmitter] = None):
        self._session_id = session_id
        self._emitter = emitter
        self._closed = False
    
    @property
    def session_id(self) -> str:
        return self._session_id
    
    def emit(self, data: Any) -> None:
        """Emit data via the emitter."""
        if self._closed:
            return
        if self._emitter and self._emitter.is_active():
            self._emitter.emit(data)
    
    def is_active(self) -> bool:
        """Check if channel is active."""
        if self._closed:
            return False
        return self._emitter is not None and self._emitter.is_active()
    
    def close(self) -> None:
        """Close the channel."""
        self._closed = True

