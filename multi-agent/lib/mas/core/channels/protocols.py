"""
Channel protocols — abstractions for session communication.

SessionChannel:        Write side — nodes emit events during execution.
SessionChannelReader:  Read side  — subscribe endpoint consumes events.
SessionStreamMonitor:  Query side — stream metadata and active sessions.
ChannelFactory:        Creates writers, readers, and monitors.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Iterator, List, Optional


class SessionChannel(ABC):
    """
    Write side of a session channel — used by nodes to emit events.
    """

    @property
    @abstractmethod
    def session_id(self) -> str: ...

    @abstractmethod
    def emit(self, data: Any) -> None:
        """
        Emit an event to the channel.

        No-op if the channel has been closed or cancelled.
        Implementations must not raise in that case.
        """
        ...

    @abstractmethod
    def is_active(self) -> bool: ...

    @abstractmethod
    def close(self, *, cancelled: bool = False) -> None: ...

    def supports_input(self) -> bool:
        return False


class InputCapableChannel(SessionChannel, ABC):
    """Extends SessionChannel with bidirectional I/O for HITL.

    ``wait_for`` blocks the calling thread until a response for the
    given *request_id* arrives (via ``submit``) or *timeout* expires.

    ``submit`` delivers a response and unblocks the waiting thread.
    Called by the inbound API layer when a human responds.

    Existing code that only needs ``emit()`` keeps using the
    ``SessionChannel`` interface — interface segregation.
    """

    @abstractmethod
    def wait_for(self, request_id: str, timeout: float) -> Optional[dict]:
        """Block until a response for *request_id* arrives.

        Returns the response dict, or ``None`` on timeout.
        Must not raise on timeout.
        """
        ...

    @abstractmethod
    def submit(self, request_id: str, data: dict) -> None:
        """Deliver a response for a pending *request_id*.

        Unblocks the corresponding ``wait_for`` call.
        """
        ...

    def supports_input(self) -> bool:
        return True


class SessionChannelReader(ABC):
    """
    Read side of a session channel — used by the subscribe endpoint
    to consume events.

    Implementations must be iterable.  Each iteration yields either:
      - a dict  → an actual event (exactly as emitted by the node)
      - None    → no new data (timeout); callers can use this for keepalives

    The iterator stops (returns) when the channel is closed.
    Data is never modified — what the node emits is what the reader yields.
    """

    @property
    @abstractmethod
    def session_id(self) -> str: ...

    @abstractmethod
    def __iter__(self) -> Iterator[Optional[dict]]: ...

    @abstractmethod
    def close(self) -> None: ...


class SessionStreamMonitor(ABC):
    """
    Read-only query interface for stream metadata.

    Backends that support distributed streaming (e.g. Redis) can
    report which sessions are active and their stream status.
    Local backends return None from the factory.
    """

    @abstractmethod
    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Return stream metadata for a session.

        Returns None if the session has no stream data.
        """
        ...

    @abstractmethod
    def list_active(self) -> List[str]:
        """Return session IDs of all currently active streams."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check whether the monitoring backend is reachable."""
        ...


class ChannelFactory(ABC):
    """
    Abstract factory for session-scoped streaming channels.

    Creates writers (always), and optionally readers and monitors
    when the backend supports cross-process communication.
    """

    @abstractmethod
    def create(self, session_id: str) -> SessionChannel:
        """Create a write channel for the given session."""
        ...

    def create_input_capable(self, session_id: str) -> Optional[InputCapableChannel]:
        """Create a bidirectional channel for HITL.

        Returns ``None`` when the backend does not support inbound
        input.  Override in subclasses that provide HITL support.
        """
        return None

    def get_input_channel(self, session_id: str) -> Optional[Any]:
        """Retrieve a submittable channel for a running session.

        Used by the API layer to push HITL approval responses into a
        session that is currently blocking on ``channel.wait_for()``.

        The returned object must expose ``submit(request_id, data)``.
        Returns ``None`` when the backend has no active channel for
        *session_id* or does not support HITL input.
        """
        return None

    def create_reader(self, session_id: str) -> Optional[SessionChannelReader]:
        """
        Create a read channel for the given session.

        Returns None when the backend does not support cross-process
        reading (e.g. LocalChannelFactory).
        """
        return None

    def create_monitor(self) -> Optional[SessionStreamMonitor]:
        """
        Return a stream monitor for querying metadata.

        Returns None when the backend does not support monitoring
        (e.g. LocalChannelFactory).
        """
        return None

