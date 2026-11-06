"""
Abstract base class for MCP transport managers.

Implements the Template Method pattern: the connect/disconnect lifecycle
is fully defined here, while subclasses supply only the transport-specific
hooks (_create_transport_context and _enter_transport_context).
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple, Any

from mcp import ClientSession

from .enums import McpTransportType

logger = logging.getLogger(__name__)


class McpConnectionError(Exception):
    """Raised when the MCP connection cannot be established or fails."""


class BaseTransportManager(ABC):
    """
    Abstract base for MCP transport managers.

    Orchestrates the full connection lifecycle:
      1) Open a protocol-specific transport context
      2) Create and initialize a ClientSession over that transport
      3) Clean disconnection of both session and transport

    Subclasses implement only the transport-specific bits via three
    abstract hooks, keeping protocol details isolated.

    Attributes:
        endpoint: MCP server endpoint URL
        sampling_callback: Optional callback for server-initiated sampling
        headers: Optional HTTP headers for authentication
    """

    def __init__(
        self,
        endpoint: str,
        sampling_callback=None,
        headers: Optional[Dict[str, str]] = None,
    ):
        """
        Initialize the transport manager.

        Args:
            endpoint: MCP server endpoint URL
            sampling_callback: Callback for server-initiated sampling requests
            headers: Optional HTTP headers for authentication or custom metadata
        """
        self.endpoint = endpoint
        self.sampling_callback = sampling_callback
        self.headers = headers or {}

        self._transport_context = None
        self._read_stream = None
        self._write_stream = None
        self._session: Optional[ClientSession] = None
        self._is_connected = False
        self._connection_attempts = 0

    # =========================================================================
    # Abstract hooks (subclass-specific)
    # =========================================================================

    @abstractmethod
    def _create_transport_context(self) -> Any:
        """
        Create the protocol-specific transport context manager (not yet entered).

        Returns:
            An async context manager that yields transport streams
        """

    @abstractmethod
    async def _enter_transport_context(self, ctx: Any) -> Tuple:
        """
        Enter the transport context and extract read/write streams.

        Args:
            ctx: The transport context manager created by _create_transport_context

        Returns:
            Tuple of (read_stream, write_stream)
        """

    @property
    @abstractmethod
    def transport_type(self) -> McpTransportType:
        """The transport protocol type this manager implements."""

    @property
    @abstractmethod
    def _transport_label(self) -> str:
        """Human-readable label for log and error messages (e.g. 'SSE')."""

    # =========================================================================
    # Shared implementation (Template Method)
    # =========================================================================

    @property
    def is_connected(self) -> bool:
        """
        Check if both transport and session are active.

        Returns:
            True if transport is open and ClientSession is initialized
        """
        return self._is_connected and self._session is not None

    async def connect(self) -> None:
        """
        Open the transport and start a ClientSession.

        Idempotent — returns immediately if already connected.
        Cleans up any half-open remnants from previous failed attempts
        before establishing a new connection.

        Raises:
            McpConnectionError: If transport or session initialization fails
        """
        if self.is_connected:
            return

        self._connection_attempts += 1
        attempt = self._connection_attempts
        is_reconnect = attempt > 1
        started_at = time.monotonic()
        logger.info(
            "mcp.stream_reconnect_start" if is_reconnect else "mcp.stream_connect_start",
            extra={
                "attempt": attempt,
                "transport": self._transport_label,
            },
        )

        await self._safe_cleanup()

        # 1) Open the protocol-specific transport
        try:
            self._transport_context = self._create_transport_context()
            self._read_stream, self._write_stream = (
                await self._enter_transport_context(self._transport_context)
            )
        except Exception as e:
            self._transport_context = None
            self._log_connection_failure(
                attempt=attempt,
                is_reconnect=is_reconnect,
                phase="transport_open",
                error=e,
                started_at=started_at,
            )
            raise McpConnectionError(
                f"{self._transport_label} transport failed: {e}"
            ) from e

        # 2) Build and initialize the MCP ClientSession
        try:
            self._session = ClientSession(
                self._read_stream,
                self._write_stream,
                sampling_callback=self.sampling_callback,
            )
            await self._session.__aenter__()
            await self._session.initialize()
        except Exception as e:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._transport_context = None
            self._session = None
            self._log_connection_failure(
                attempt=attempt,
                is_reconnect=is_reconnect,
                phase="session_initialize",
                error=e,
                started_at=started_at,
            )
            raise McpConnectionError(
                f"ClientSession initialization failed: {e}"
            ) from e

        self._is_connected = True
        logger.info(
            "mcp.stream_reconnect_success" if is_reconnect else "mcp.stream_connect_success",
            extra={
                "attempt": attempt,
                "transport": self._transport_label,
                "latency_ms": round((time.monotonic() - started_at) * 1000),
            },
        )

    def _log_connection_failure(
        self,
        *,
        attempt: int,
        is_reconnect: bool,
        phase: str,
        error: Exception,
        started_at: float,
    ) -> None:
        logger.error(
            "mcp.stream_reconnect_failed" if is_reconnect else "mcp.stream_connect_failed",
            extra={
                "attempt": attempt,
                "transport": self._transport_label,
                "phase": phase,
                "latency_ms": round((time.monotonic() - started_at) * 1000),
                "exception_type": type(error).__name__,
                "exception_message": str(error),
            },
            exc_info=(type(error), error, error.__traceback__),
        )

    async def disconnect(self) -> None:
        """
        Cleanly close the ClientSession and then the transport.

        No-op if not connected. Marks disconnected immediately to
        prevent re-entry races before teardown begins.
        """
        if not self.is_connected:
            return

        self._is_connected = False

        # 1) Close ClientSession
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except (RuntimeError, GeneratorExit):
                pass
            except Exception:
                pass
            finally:
                self._session = None

        # 2) Close transport context
        if self._transport_context:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except (RuntimeError, GeneratorExit):
                pass
            except Exception:
                pass
            finally:
                self._transport_context = None
                self._read_stream = None
                self._write_stream = None

        logger.debug(
            "mcp.stream_disconnected",
            extra={"transport": self._transport_label, "attempt": self._connection_attempts},
        )

    async def _safe_cleanup(self) -> None:
        """
        Tear down any half-open session or transport quietly.

        Called at the start of connect() to avoid leaving resources
        from a previous failed attempt.
        """
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        if self._transport_context:
            try:
                await self._transport_context.__aexit__(None, None, None)
            except Exception:
                pass
            self._transport_context = None
            self._read_stream = None
            self._write_stream = None

    # =========================================================================
    # Context manager protocol
    # =========================================================================

    async def __aenter__(self):
        """Connect on entering ``async with`` block."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Disconnect on exiting ``async with`` block."""
        await self.disconnect()
