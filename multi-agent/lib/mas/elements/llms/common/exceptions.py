"""Typed errors raised by LLM providers.

These let callers distinguish *expected, non-fatal* provider conditions
(such as a rate limit or quota rejection) from genuine failures.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

#: ``type`` value of the structured error attached to message / result metadata.
RATE_LIMITED_TYPE = "rate_limited"


class LLMRateLimitError(Exception):
    """The model endpoint rejected the call with HTTP 429.

    Not a crash: the request was well formed, the caller is simply over a
    rate limit or quota.  Retrying immediately will not help.

    Attributes:
        detail: Human-readable reason from the endpoint, when provided.
        retry_after: Seconds to wait before retrying, when the endpoint
            sent a ``Retry-After`` header.
        status_code: Always 429.
    """

    status_code = 429
    #: Retrying inside the agent loop is pointless.
    recoverable = False

    def __init__(self, detail: str | None = None, retry_after: float | None = None) -> None:
        self.detail = detail or "The model endpoint is rate limiting requests."
        self.retry_after = retry_after
        super().__init__(self.detail)

    def user_message(self) -> str:
        msg = f"Rate limit reached: {self.detail}"
        if self.retry_after is not None:
            msg += f" Please retry in {format_delay(self.retry_after)}."
        return msg

    def to_dict(self) -> dict[str, Any]:
        """Structured form carried in metadata (``ERROR_METADATA_KEY``)."""
        return {
            "type": RATE_LIMITED_TYPE,
            "message": self.user_message(),
            "retry_after": self.retry_after,
        }

    def __str__(self) -> str:
        return self.user_message()


def format_delay(seconds: float) -> str:
    seconds = max(0, math.ceil(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}min" if rest == 0 else f"{minutes}min {rest}s"


def parse_retry_after(value: str | None) -> float | None:
    """Parse a ``Retry-After`` header (delta-seconds or HTTP-date)."""
    if not value:
        return None
    value = value.strip()
    try:
        seconds = float(value)
        return seconds if seconds >= 0 else None
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        when = when.replace(tzinfo=UTC)
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def extract_error_detail(body: Any) -> str | None:
    """Best-effort human text from an error body (OpenAI or FastAPI style)."""
    if isinstance(body, str):
        return body.strip() or None
    if not isinstance(body, Mapping):
        return None
    for key in ("detail", "error", "message"):
        val = body.get(key)
        if isinstance(val, str) and val.strip():
            extras = ", ".join(
                f"{k}={v}"
                for k, v in body.items()
                if k != key and isinstance(v, (str, int, float)) and not isinstance(v, bool)
            )
            return f"{val.strip()} ({extras})" if extras else val.strip()
        if isinstance(val, Mapping):
            inner = extract_error_detail(val)
            if inner:
                return inner
    return None


def rate_limit_from_response(
    headers: Mapping[str, str] | None, body: Any
) -> LLMRateLimitError:
    retry = parse_retry_after(headers.get("retry-after") if headers else None)
    return LLMRateLimitError(extract_error_detail(body), retry)
