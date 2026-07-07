"""
File attachment model and helpers.

Cross-cutting shared type consumed by elements, session, graph, and adapters.
Same pattern as Identity (mas.core.identity) and ExecutionContext (mas.core.execution_context).
"""
from datetime import datetime, timezone, timedelta
from typing import List, Tuple

from pydantic import BaseModel, ConfigDict

FILE_ATTACHMENT_TTL_HOURS = 48


class FileAttachment(BaseModel):
    """Immutable reference to a file uploaded via an external file service."""

    file_name: str
    mime_type: str
    file_uri: str
    size_bytes: int
    uploaded_at: str

    model_config = ConfigDict(frozen=True)


def coerce_attachments(raw: list) -> List[FileAttachment]:
    """Coerce a list of dicts or FileAttachment objects to typed FileAttachment.

    Workspace variables store attachments as plain dicts after serialisation.
    Call this at every deserialization boundary to ensure typed access downstream.
    """
    if not raw:
        return []
    return [
        att if isinstance(att, FileAttachment) else FileAttachment.model_validate(att)
        for att in raw
    ]


def is_attachment_active(att: FileAttachment) -> bool:
    """Check if a single attachment is within the TTL window."""
    if not att.uploaded_at:
        return True
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(att.uploaded_at)
        return elapsed < timedelta(hours=FILE_ATTACHMENT_TTL_HOURS)
    except (ValueError, TypeError):
        return True


def filter_active_attachments(attachments: List[FileAttachment]) -> List[FileAttachment]:
    """Return only non-expired attachments (within TTL window)."""
    if not attachments:
        return []
    return [att for att in attachments if is_attachment_active(att)]


def partition_attachments(
    attachments: List[FileAttachment],
) -> Tuple[List[FileAttachment], List[FileAttachment]]:
    """Split attachments into (active, expired) lists."""
    if not attachments:
        return [], []
    active: List[FileAttachment] = []
    expired: List[FileAttachment] = []
    for att in attachments:
        (active if is_attachment_active(att) else expired).append(att)
    return active, expired


def format_attachment_lines(
    attachments: List[FileAttachment], prefix: str = "- "
) -> List[str]:
    """Format attachments as display lines for prompt injection.

    Args:
        attachments: List of FileAttachment objects.
        prefix: Line prefix (e.g. ``"- "`` or ``"  - "`` for indentation).

    Returns:
        List of formatted strings, one per attachment.
    """
    return [
        f"{prefix}{att.file_name} ({att.mime_type}) -> {att.file_uri}"
        for att in attachments
    ]
