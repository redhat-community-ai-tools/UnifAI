"""
Local channel factory for same-process execution.

Creates matched writer+reader pairs backed by a shared ``queue.Queue``.
The factory keeps a registry of queues so that ``create()`` and
``create_reader()`` for the same session_id share the same queue.

``create_input_capable()`` returns a ``LocalInputCapableChannel``
that supports bidirectional HITL communication within the same process.
"""
import queue
from typing import Dict, Optional

from mas.core.channels import (
    ChannelFactory,
    InputCapableChannel,
    SessionChannel,
    SessionChannelReader,
)
from .channel import LocalSessionChannel, LocalSessionChannelReader
from .input_channel import LocalInputCapableChannel


class LocalChannelFactory(ChannelFactory):

    def __init__(self) -> None:
        self._queues: Dict[str, queue.Queue] = {}
        self._input_channels: Dict[str, LocalInputCapableChannel] = {}

    def _get_or_create_queue(self, session_id: str) -> queue.Queue:
        if session_id not in self._queues:
            self._queues[session_id] = queue.Queue()
        return self._queues[session_id]

    def create(self, session_id: str) -> SessionChannel:
        q = self._get_or_create_queue(session_id)
        return LocalSessionChannel(session_id=session_id, event_queue=q)

    def create_input_capable(self, session_id: str) -> Optional[InputCapableChannel]:
        q = self._get_or_create_queue(session_id)
        channel = LocalInputCapableChannel(session_id=session_id, event_queue=q)
        self._input_channels[session_id] = channel
        return channel

    def get_input_channel(self, session_id: str) -> Optional[LocalInputCapableChannel]:
        """Retrieve a previously created input-capable channel.

        Used by the API layer to call ``submit()`` on a channel that
        a running session is currently blocking on.
        """
        return self._input_channels.get(session_id)

    def create_reader(self, session_id: str) -> Optional[SessionChannelReader]:
        q = self._get_or_create_queue(session_id)
        return LocalSessionChannelReader(session_id=session_id, event_queue=q)
