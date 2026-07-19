"""
HITL ports — abstract contracts implemented by adapters.

ApprovalGate:        ask a human and wait for a decision.
ApprovalGateFactory: create a gate + policy from a channel and session.
OverridesStore:      shared store for live auto-approval overrides.

Uses the Template Method pattern: the base class owns timeout handling
so that every adapter inherits consistent behaviour.  Subclasses only
implement ``_send_and_wait``.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional

from mas.core.hitl.models import (
    ApprovalOverrides,
    ApprovalRequest,
    ApprovalResponse,
    HITLConfig,
    ToolApprovalPolicy,
)


class ApprovalGate(ABC):
    """Port: sends a request to a human and blocks until a decision arrives.

    Timeout logic lives in the base class (template method) so that
    all adapters share the same behaviour controlled by ``HITLConfig``.
    """

    def __init__(self, config: HITLConfig) -> None:
        self._config = config

    @abstractmethod
    def _send_and_wait(
        self,
        request: ApprovalRequest,
        timeout: float,
    ) -> ApprovalResponse | None:
        """Adapter hook — emit the request and block until a response arrives.

        Return ``None`` when *timeout* seconds elapse without a response.
        Implementations must not raise on timeout — they return ``None``.
        """
        ...

    def request_approval(self, request: ApprovalRequest) -> ApprovalResponse:
        """Template method — delegates to ``_send_and_wait`` then applies
        the timeout policy from ``HITLConfig`` if no response arrives."""
        response = self._send_and_wait(
            request,
            timeout=self._config.timeout_seconds,
        )
        if response is not None:
            return response
        return ApprovalResponse(
            request_id=request.request_id,
            decision=self._config.timeout_decision,
            feedback=self._config.timeout_feedback,
        )


class ApprovalGateFactory(ABC):
    """Port: creates an ApprovalGate + ToolApprovalPolicy for a session run.

    The domain runner depends on this abstraction; the adapter provides
    the concrete wiring (which gate implementation, which decorator,
    where to read overrides from).

    Returns ``(None, None)`` when HITL is not available for the given
    channel (e.g. channel does not support input).
    """

    @abstractmethod
    def create(
        self,
        channel: Any,
        session_metadata: Any,
        run_id: str,
    ) -> tuple[Optional[ApprovalGate], Optional[ToolApprovalPolicy]]:
        """Build a gate + policy pair for one execution run.

        Args:
            channel: The session channel (may or may not be InputCapable).
            session_metadata: The session's metadata (carries hitl_overrides).
            run_id: The session run ID (used for gate registry lookup).
        """
        ...

    def remove(self, run_id: str) -> None:
        """Clean up any resources associated with *run_id* after execution.

        Default is a no-op; override when the factory maintains state
        (e.g. a gate registry).
        """


class OverridesStore(ABC):
    """Port: shared store for live auto-approval overrides.

    Decouples the API layer (which writes rules) from the execution
    layer (which reads them).  Works across process boundaries
    (e.g. Flask server ↔ Temporal worker) when backed by Redis.
    """

    @abstractmethod
    def load(self, session_id: str) -> ApprovalOverrides:
        """Read the current overrides for a session.

        Returns an empty ``ApprovalOverrides`` when no overrides exist.
        """
        ...

    @abstractmethod
    def save(self, session_id: str, overrides: ApprovalOverrides) -> None:
        """Write overrides for a session, replacing any previous value."""
        ...

    @abstractmethod
    def remove(self, session_id: str) -> None:
        """Delete overrides for a session (cleanup after run completes)."""
        ...
