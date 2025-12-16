"""
LangGraph-specific stream emitter.
Wraps LangGraph's get_stream_writer().
"""
from typing import Any, Optional, Callable
from langgraph.config import get_stream_writer
from core.channels import StreamEmitter


class LangGraphEmitter(StreamEmitter):
    """
    Emitter that uses LangGraph's internal stream writer.
    Only active when LangGraph is in streaming mode.
    """
    
    def __init__(self):
        self._writer: Optional[Callable[[Any], None]] = None
        self._active = False
    
    def _activate(self) -> None:
        """
        Activate by fetching writer from LangGraph context.
        Called lazily on first emit.
        """
        if self._active:
            return
        try:
            self._writer = get_stream_writer()
            self._active = self._writer is not None
        except Exception:
            self._writer = None
            self._active = False
    
    def emit(self, data: Any) -> None:
        """Emit data via LangGraph's stream writer."""
        if not self._active:
            self._activate()
        if self._writer:
            self._writer(data)
    
    def is_active(self) -> bool:
        """Check if LangGraph streaming is active."""
        if not self._active:
            self._activate()
        return self._active

