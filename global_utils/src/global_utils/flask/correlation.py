"""HTTP / async correlation helpers for request_id and session_id."""
from __future__ import annotations

import uuid
from typing import Any, Mapping, Optional

from global_utils.utils.logging_config import (
    get_request_id,
    get_session_id,
    set_request_id,
    set_session_id,
)

REQUEST_ID_HEADER = "X-Request-ID"


def resolve_incoming_request_id(headers: Mapping[str, Any]) -> str:
    """Read X-Request-ID or generate ``req-<hex>``."""
    raw = headers.get(REQUEST_ID_HEADER)
    if raw is None and hasattr(headers, "get"):
        # Werkzeug EnvironHeaders are case-insensitive; try lowercase key too
        raw = headers.get(REQUEST_ID_HEADER.lower())
    if isinstance(raw, (list, tuple)):
        raw = raw[0] if raw else None
    if raw:
        value = str(raw).strip()
        if value:
            return value
    return f"req-{uuid.uuid4().hex}"


def correlation_headers() -> dict[str, str]:
    """Outbound headers carrying the current request_id, if bound."""
    request_id = get_request_id()
    if not request_id:
        return {}
    return {REQUEST_ID_HEADER: request_id}


def bind_request_id_from_headers(headers: Mapping[str, Any]) -> str:
    """Resolve and bind request_id from inbound headers. Returns the id."""
    request_id = resolve_incoming_request_id(headers)
    set_request_id(request_id)
    return request_id


def bind_session_id(session_id: Optional[str]) -> None:
    """Bind session_id when a non-empty string is provided."""
    if session_id:
        set_session_id(str(session_id))


def clear_correlation_context() -> None:
    """Clear request_id and session_id after an HTTP request completes."""
    set_request_id(None)
    set_session_id(None)


def celery_correlation_headers() -> dict[str, str]:
    """Celery task headers from the current context (omit unset)."""
    headers: dict[str, str] = {}
    request_id = get_request_id()
    session_id = get_session_id()
    if request_id:
        headers["request_id"] = request_id
    if session_id:
        headers["session_id"] = session_id
    return headers


def bind_from_celery_headers(headers: Optional[Mapping[str, Any]]) -> None:
    """Bind ContextVars from Celery task headers."""
    if not headers:
        return
    request_id = headers.get("request_id")
    session_id = headers.get("session_id")
    if request_id:
        set_request_id(str(request_id))
    if session_id:
        set_session_id(str(session_id))
