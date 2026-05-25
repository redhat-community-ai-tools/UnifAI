"""
Outbound ports for session execution.

Ports are defined by the use-case owner (session layer) and implemented
by infrastructure adapters.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List

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


# ── File Upload Port ──────────────────────────────────────────────────


class FileUploadError(Exception):
    """Raised when file upload fails after exhausting retries.

    Adapters MUST wrap vendor-specific exceptions into this type.
    The message should be user-presentable.
    """

    def __init__(self, message: str, failed_file: str = "", retriable: bool = False):
        self.failed_file = failed_file
        self.retriable = retriable
        super().__init__(message)


@dataclass(frozen=True)
class FileUploadRequest:
    """Single file to upload — input DTO for the port."""
    file_name: str
    file_bytes: bytes
    mime_type: str


@dataclass(frozen=True)
class FileUploadResult:
    """Successful upload reference — output DTO from the port."""
    file_name: str
    mime_type: str
    file_uri: str
    size_bytes: int


@dataclass(frozen=True)
class FileUploadLimits:
    """Authoritative upload constraints — shared between adapter validation and UI hints."""
    max_files: int = 3
    max_file_size_bytes: int = 20 * 1024 * 1024
    min_file_size_bytes: int = 1
    allowed_mime_types: tuple = (
        "application/pdf", "text/csv", "text/plain", "text/html", "text/markdown",
    )


class IFileUploadService(ABC):
    """Outbound port for file upload operations."""

    @abstractmethod
    def upload_batch(self, files: List[FileUploadRequest]) -> List[FileUploadResult]:
        """Upload multiple files atomically.

        Returns results in the same order as the input list.
        If any upload fails, the adapter cleans up already-uploaded
        files and raises FileUploadError.
        """
        ...
