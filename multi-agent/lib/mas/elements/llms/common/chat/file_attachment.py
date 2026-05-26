from datetime import datetime, timezone, timedelta
from typing import Any, List, Tuple

from pydantic import BaseModel, ConfigDict

FILE_ATTACHMENT_TTL_HOURS = 48


def get_attachment_field(att: Any, key: str, default: str = "") -> str:
    """Read a field from a dict or Pydantic object uniformly.

    File attachments travel through the system as both ``FileAttachment``
    model instances (in graph state) and plain dicts (in workspace
    variables after serialisation).  This helper allows callers to read
    fields without caring about the concrete representation.
    """
    if isinstance(att, dict):
        return att.get(key, default)
    return getattr(att, key, default)


def is_attachment_active(att: Any) -> bool:
    """Check if a single attachment is within the TTL window."""
    uploaded_at = get_attachment_field(att, "uploaded_at", "")
    if not uploaded_at:
        return True
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(uploaded_at)
        return elapsed < timedelta(hours=FILE_ATTACHMENT_TTL_HOURS)
    except (ValueError, TypeError):
        return True


def filter_active_attachments(attachments: list) -> list:
    """Return only non-expired attachments (within TTL window)."""
    if not attachments:
        return []
    return [att for att in attachments if is_attachment_active(att)]


def partition_attachments(attachments: list) -> Tuple[list, list]:
    """Split attachments into (active, expired) lists."""
    if not attachments:
        return [], []
    active, expired = [], []
    for att in attachments:
        (active if is_attachment_active(att) else expired).append(att)
    return active, expired


def format_attachment_lines(attachments: list, prefix: str = "- ") -> List[str]:
    """Format attachments as display lines for prompt injection.

    Args:
        attachments: List of attachment dicts or FileAttachment objects.
        prefix: Line prefix (e.g. ``"- "`` or ``"  - "`` for indentation).

    Returns:
        List of formatted strings, one per attachment.
    """
    return [
        f"{prefix}{get_attachment_field(att, 'file_name')} "
        f"({get_attachment_field(att, 'mime_type')}) -> "
        f"{get_attachment_field(att, 'file_uri')}"
        for att in attachments
    ]


class FileAttachment(BaseModel):
    """Immutable reference to a file uploaded via an external file service."""

    file_name: str
    mime_type: str
    file_uri: str
    size_bytes: int
    uploaded_at: str

    model_config = ConfigDict(frozen=True)
