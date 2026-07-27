"""
Outbound ports for session execution.

Ports are defined by the use-case owner (session layer) and implemented
by infrastructure adapters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from mas.session.domain.workflow_session import WorkflowSession
from mas.core.execution_context import ExecutionContext


@dataclass(frozen=True)
class SubmitSessionRequest:
    """Immutable value object carrying execution context for a background worker.

    Inputs are already staged into the SessionRecord before submission,
    so this only carries the execution context (scope, user, etc.).
    The engine handle lives in execution_context.engine_handle.
    """
    execution_context: ExecutionContext = field(default_factory=ExecutionContext)


class BackgroundSessionEngine(ABC):
    """
    Outbound port for background workflow operations on a session.

    Each infrastructure adapter (Temporal, Celery, …) implements this port.
    Lifecycle transitions and channel cleanup remain in BackgroundLifecycleHandler —
    this port only handles workflow-level commands.
    """

    @abstractmethod
    def generate_handle(self, session_id: str) -> str:
        """Pre-generate a unique handle for the background workflow.

        Called before submit() so the handle can be persisted atomically
        with input staging, eliminating the race window between workflow
        start and handle persistence.
        """
        ...

    @abstractmethod
    def submit(self, session: WorkflowSession, request: SubmitSessionRequest) -> None:
        """Start background execution.

        The engine handle is read from request.execution_context.engine_handle.
        """
        ...

    @abstractmethod
    def cancel(self, handle: str) -> None:
        """Request cancellation of a running background session."""
        ...
