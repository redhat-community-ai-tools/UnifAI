"""
Streaming capability mixin for nodes.
Provides streaming functionality via SessionChannel abstraction.
"""
from typing import Any, Mapping, Optional
from core.channels import SessionChannel


class StreamingCapableMixin:
    """
    Mixin that provides streaming capability to nodes.
    
    Provides:
        - set_streaming_channel(channel): Inject channel before execution
        - _stream(payload): Emit enriched data
        - is_streaming(): Check if streaming is active
    
    Usage:
        class MyNode(StreamingCapableMixin, BaseNode):
            def run(self, state):
                self._stream({"type": "progress", "value": 50})
                ...
    """
    
    _streaming_channel: Optional[SessionChannel] = None
    
    def set_streaming_channel(self, channel: Optional[SessionChannel]) -> None:
        """Inject the streaming channel before execution."""
        self._streaming_channel = channel
    
    def _stream(self, payload: Mapping[str, Any]) -> None:
        """
        Emit data to the streaming channel.
        Enriches payload with node metadata if _base_stream_data() is available.
        """
        if self._streaming_channel is None:
            return
        if not self._streaming_channel.is_active():
            return
        
        # Enrich with node metadata if available
        enriched: dict[str, Any] = dict(payload)
        if hasattr(self, '_base_stream_data'):
            enriched = {**self._base_stream_data(), **payload}
        
        self._streaming_channel.emit(enriched)
    
    def is_streaming(self) -> bool:
        """Check if streaming is active."""
        return (
            self._streaming_channel is not None 
            and self._streaming_channel.is_active()
        )

