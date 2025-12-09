"""
A2A Response Handlers.

Each handler auto-registers via BaseHandler.__init_subclass__.
Handles SUCCESS response types only. Errors handled directly by client.
"""

from a2a.types import (
    Task,
    Message,
    TaskStatusUpdateEvent,
    TaskArtifactUpdateEvent,
)

from .base_handler import BaseHandler
from elements.providers.a2a_client.result import A2AResult, ResultKind


class TaskHandler(BaseHandler):
    """Handles Task responses."""

    handled_types = {Task}

    def convert(self, obj: Task, is_streaming: bool = False) -> A2AResult:
        return A2AResult(
            kind=ResultKind.TASK,
            task=obj,
            task_id=obj.id,
            context_id=obj.context_id,
            is_streaming=is_streaming,
        )


class MessageHandler(BaseHandler):
    """Handles immediate Message responses."""

    handled_types = {Message}

    def convert(self, obj: Message, is_streaming: bool = False) -> A2AResult:
        return A2AResult(
            kind=ResultKind.MESSAGE,
            message=obj,
            task_id=obj.task_id,
            context_id=obj.context_id,
            is_streaming=is_streaming,
        )


class StatusEventHandler(BaseHandler):
    """Handles TaskStatusUpdateEvent from streaming."""

    handled_types = {TaskStatusUpdateEvent}

    def convert(self, obj: TaskStatusUpdateEvent, is_streaming: bool = False) -> A2AResult:
        return A2AResult(
            kind=ResultKind.STATUS_EVENT,
            status_event=obj,
            task_id=obj.task_id,
            context_id=obj.context_id,
            is_streaming=True,
        )


class ArtifactEventHandler(BaseHandler):
    """Handles TaskArtifactUpdateEvent from streaming."""

    handled_types = {TaskArtifactUpdateEvent}

    def convert(self, obj: TaskArtifactUpdateEvent, is_streaming: bool = False) -> A2AResult:
        return A2AResult(
            kind=ResultKind.ARTIFACT_EVENT,
            artifact_event=obj,
            task_id=obj.task_id,
            context_id=obj.context_id,
            is_streaming=True,
        )
