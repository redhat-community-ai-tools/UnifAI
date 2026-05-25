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

    Future: add request_input() for HITL.
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

