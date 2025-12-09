"""
A2AResult - Unified wrapper for all A2A SDK response types.

Provides consistent interface regardless of whether response is:
- Task (from send or get)
- Message (immediate response)
- TaskStatusUpdateEvent (streaming status)
- TaskArtifactUpdateEvent (streaming content)
- Error
"""

from enum import Enum
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field

from a2a.types import (
    Task,
    Message,
    TaskState,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
    Artifact,
    JSONRPCError,
)


class ResultKind(str, Enum):
    """Discriminator for A2A result type."""
    TASK = "task"
    MESSAGE = "message"
    STATUS_EVENT = "status_event"
    ARTIFACT_EVENT = "artifact_event"
    ERROR = "error"


class A2AResult(BaseModel):
    """
    Unified result wrapping any A2A SDK response type.
    
    Provides consistent interface regardless of source.
    Uses SDK types directly - no duplication.
    """

    kind: ResultKind

    task: Optional[Task] = None
    message: Optional[Message] = None
    status_event: Optional[TaskStatusUpdateEvent] = None
    artifact_event: Optional[TaskArtifactUpdateEvent] = None
    error: Optional[JSONRPCError] = None

    task_id: Optional[str] = None
    context_id: Optional[str] = None

    error_message: Optional[str] = None
    error_code: Optional[int] = None

    is_streaming: bool = False

    model_config = {"arbitrary_types_allowed": True}

    @property
    def state(self) -> Optional[TaskState]:
        """Get TaskState from any result type."""
        if self.task and self.task.status:
            return self.task.status.state
        if self.status_event and self.status_event.status:
            return self.status_event.status.state
        return None

    @property
    def is_terminal(self) -> bool:
        """True if this is a terminal state."""
        if self.kind in (ResultKind.MESSAGE, ResultKind.ERROR):
            return True
        state = self.state
        if state is None:
            return False
        return state in TERMINAL_STATES

    @property
    def is_complete(self) -> bool:
        """True if work is complete."""
        if self.kind == ResultKind.MESSAGE:
            return True
        if self.kind == ResultKind.ERROR:
            return True
        if self.status_event and self.status_event.final:
            return True
        return self.is_terminal

    @property
    def is_success(self) -> bool:
        """True if successfully completed."""
        return self.state == TaskState.completed

    @property
    def is_failure(self) -> bool:
        """True if failed or rejected."""
        if self.kind == ResultKind.ERROR:
            return True
        state = self.state
        return state in (TaskState.failed, TaskState.rejected) if state else False

    @property
    def is_canceled(self) -> bool:
        """True if task was canceled."""
        return self.state == TaskState.canceled

    @property
    def is_error(self) -> bool:
        """True if this is an error result."""
        return self.kind == ResultKind.ERROR

    @property
    def is_working(self) -> bool:
        """True if task is still working."""
        return self.state == TaskState.working

    @property
    def is_submitted(self) -> bool:
        """True if task is submitted but not started."""
        return self.state == TaskState.submitted

    @property
    def requires_input(self) -> bool:
        """True if additional input is required."""
        return self.state == TaskState.input_required

    @property
    def requires_auth(self) -> bool:
        """True if authentication is required."""
        return self.state == TaskState.auth_required

    @property
    def artifacts(self) -> List[Artifact]:
        """Get artifacts from any result type."""
        if self.task and self.task.artifacts:
            return self.task.artifacts
        if self.artifact_event and self.artifact_event.artifact:
            return [self.artifact_event.artifact]
        return []

    @property
    def status_message_obj(self) -> Optional[Message]:
        """Get status message if available."""
        if self.task and self.task.status:
            return self.task.status.message
        if self.status_event and self.status_event.status:
            return self.status_event.status.message
        return None

    @property
    def is_append(self) -> bool:
        """For artifact events: should append to existing artifact."""
        if self.artifact_event:
            return self.artifact_event.append or False
        return False

    @property
    def is_last_chunk(self) -> bool:
        """For artifact events: is this the last chunk."""
        if self.artifact_event:
            return self.artifact_event.last_chunk or False
        return False

    @classmethod
    def from_task(cls, task: Task, is_streaming: bool = False) -> "A2AResult":
        """Create from SDK Task."""
        return cls(
            kind=ResultKind.TASK,
            task=task,
            task_id=task.id,
            context_id=task.context_id,
            is_streaming=is_streaming,
        )

    @classmethod
    def from_message(cls, message: Message, is_streaming: bool = False) -> "A2AResult":
        """Create from SDK Message."""
        return cls(
            kind=ResultKind.MESSAGE,
            message=message,
            task_id=message.task_id,
            context_id=message.context_id,
            is_streaming=is_streaming,
        )

    @classmethod
    def from_status_event(cls, event: TaskStatusUpdateEvent) -> "A2AResult":
        """Create from SDK TaskStatusUpdateEvent."""
        return cls(
            kind=ResultKind.STATUS_EVENT,
            status_event=event,
            task_id=event.task_id,
            context_id=event.context_id,
            is_streaming=True,
        )

    @classmethod
    def from_artifact_event(cls, event: TaskArtifactUpdateEvent) -> "A2AResult":
        """Create from SDK TaskArtifactUpdateEvent."""
        return cls(
            kind=ResultKind.ARTIFACT_EVENT,
            artifact_event=event,
            task_id=event.task_id,
            context_id=event.context_id,
            is_streaming=True,
        )

    @classmethod
    def from_error(
            cls,
            error: Optional[JSONRPCError] = None,
            message: Optional[str] = None,
            code: Optional[int] = None,
            task_id: Optional[str] = None,
    ) -> "A2AResult":
        """Create from error."""
        return cls(
            kind=ResultKind.ERROR,
            error=error,
            error_message=message or (error.message if error else "Unknown error"),
            error_code=code or (error.code if error else None),
            task_id=task_id,
        )


TERMINAL_STATES = frozenset({
    TaskState.completed,
    TaskState.failed,
    TaskState.canceled,
    TaskState.rejected,
})
