"""
Queue-based local session channel (writer + reader).

Uses a shared ``queue.Queue`` so that writer and reader work across
threads within the same process.  The writer (LocalSessionChannel) is
injected into nodes; the reader (LocalSessionChannelReader) is
consumed by ForegroundSessionRunner to yield events to the client.

This replaces the old LangGraphEmitter-based circular approach.
"""
import queue
import logging
from typing import Any, Iterator, Optional

from mas.core.channels import SessionChannel, SessionChannelReader

logger = logging.getLogger(__name__)

_CLOSE = object()


class LocalSessionChannel(SessionChannel):
    """Write side — nodes call ``emit()`` to push events into the queue."""

    def __init__(self, session_id: str, event_queue: queue.Queue) -> None:
        self._session_id = session_id
        self._queue = event_queue
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._session_id

    def emit(self, data: Any) -> None:
        if self._closed:
            return
        self._queue.put(("data", data))

    def is_active(self) -> bool:
        return not self._closed

    def close(self, *, cancelled: bool = False) -> None:
        if self._closed:
            return
        self._closed = True
        self._queue.put((_CLOSE, None))


class LocalSessionChannelReader(SessionChannelReader):
    """Read side — iterates events from the shared queue until closed."""

    def __init__(self, session_id: str, event_queue: queue.Queue, timeout: float = 5.0) -> None:
        self._session_id = session_id
        self._queue = event_queue
        self._timeout = timeout
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._session_id

    def __iter__(self) -> Iterator[Optional[dict]]:
        while not self._closed:
            try:
                tag, value = self._queue.get(timeout=self._timeout)
            except queue.Empty:
                yield None
                continue

            if tag is _CLOSE:
                return
            yield value

    def close(self) -> None:
        self._closed = True
