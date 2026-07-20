"""
Local input-capable session channel for same-process HITL.

Extends ``LocalSessionChannel`` with bidirectional I/O using
``threading.Event`` + a shared dict.  ``wait_for`` blocks the
graph thread; ``submit`` (called from the Flask request thread)
unblocks it.

Thread-safety is achieved through the ``threading.Lock`` that
guards the pending-requests map.
"""
import logging
import queue
import threading
from typing import Any, Optional

from mas.core.channels import InputCapableChannel

logger = logging.getLogger(__name__)

_CLOSE = object()


class LocalInputCapableChannel(InputCapableChannel):
    """Bidirectional local channel — outbound events via queue,
    inbound HITL responses via threading.Event signalling."""

    def __init__(self, session_id: str, event_queue: queue.Queue) -> None:
        self._session_id = session_id
        self._queue = event_queue
        self._closed = False

        self._pending_lock = threading.Lock()
        self._pending_events: dict[str, threading.Event] = {}
        self._pending_responses: dict[str, dict] = {}

    # -- SessionChannel (outbound) -----------------------------------------

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
        self._release_all_waiters()

    # -- InputCapableChannel (inbound HITL) ---------------------------------

    def wait_for(self, request_id: str, timeout: float) -> Optional[dict]:
        event = threading.Event()
        with self._pending_lock:
            self._pending_events[request_id] = event

        signalled = event.wait(timeout=timeout)

        with self._pending_lock:
            self._pending_events.pop(request_id, None)
            if signalled:
                return self._pending_responses.pop(request_id, None)
            self._pending_responses.pop(request_id, None)
            return None

    def submit(self, request_id: str, data: dict) -> None:
        with self._pending_lock:
            self._pending_responses[request_id] = data
            event = self._pending_events.get(request_id)
        if event is not None:
            event.set()
        else:
            logger.warning(
                "submit() for unknown request_id %s on session %s",
                request_id, self._session_id,
            )

    # -- Internal -----------------------------------------------------------

    def _release_all_waiters(self) -> None:
        """Unblock every pending wait_for on channel close."""
        with self._pending_lock:
            for event in self._pending_events.values():
                event.set()
