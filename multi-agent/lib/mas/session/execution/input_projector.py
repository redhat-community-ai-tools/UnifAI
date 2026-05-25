"""
Session input projector — stages a user turn into the SessionRecord.

Responsibility (SRP):
  • Map raw external inputs onto GraphState channels
  • Mirror user_prompt into the messages conversation history
  • Upload attached files via the file upload port
  • Derive a human-readable title when missing
  • Transition status to QUEUED
  • Persist the staged record

This runs synchronously at the service boundary — BEFORE any
execution engine (foreground or background) touches the record.
After staging, the UI can immediately read messages from the DB.
"""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from mas.elements.llms.common.chat.file_attachment import FileAttachment
from mas.elements.llms.common.chat.message import ChatMessage, Role
from mas.session.domain.session_record import SessionRecord
from mas.session.domain.status import SessionStatus
from mas.session.execution.ports import FileUploadRequest, IFileUploadService
from mas.session.domain.constants import CANCELLED_TAG
from mas.session.management.utils import derive_title
from mas.session.repository.repository import SessionRepository


class SessionInputProjector:
    """
    Stages raw user inputs into a SessionRecord and persists it.

    Stateless — all state lives in the SessionRecord and the repository.
    """

    def __init__(
        self,
        repository: SessionRepository,
        file_upload_service: Optional[IFileUploadService] = None,
    ) -> None:
        self._repo = repository
        self._file_upload_service = file_upload_service

    @property
    def supports_file_upload(self) -> bool:
        """Whether a file upload service is configured."""
        return self._file_upload_service is not None

    def apply(
        self,
        record: SessionRecord,
        inputs: Dict[str, Any],
        logged_in_user: str = "",
        files: Optional[List[FileUploadRequest]] = None,
    ) -> None:
        """
        Project raw inputs onto the record's graph state, making the
        user turn immediately durable.

        Idempotent with respect to title derivation (skips if already set).
        """
        if record.metadata.title is None:
            if title := derive_title(inputs):
                record.metadata.title = title

        record.graph_state.update(inputs)

        attachments: List[FileAttachment] = []
        if files and self._file_upload_service:
            results = self._file_upload_service.upload_batch(files)
            now = datetime.now(timezone.utc).isoformat()
            attachments = [
                FileAttachment(
                    file_name=r.file_name,
                    mime_type=r.mime_type,
                    file_uri=r.file_uri,
                    size_bytes=r.size_bytes,
                    uploaded_at=now,
                )
                for r in results
            ]
            record.graph_state.file_attachments = attachments

        prompt = (inputs.get("user_prompt") or "").strip()
        if prompt:
            record.graph_state.messages.append(
                ChatMessage(
                    role=Role.USER,
                    content=prompt,
                    file_attachments=attachments or None,
                    sender_id=logged_in_user or None,
                )
            )

        # Persist acting user for OAuth on the durable record so Temporal / workers always
        # see tags after reload. with_credential_user() rejects team ids automatically.
        record.run_context = record.run_context.with_credential_user(logged_in_user)

        record.metadata.status_message = None
        record.metadata.tags.pop(CANCELLED_TAG, None)
        record.status = SessionStatus.QUEUED
        self._repo.save(record)
