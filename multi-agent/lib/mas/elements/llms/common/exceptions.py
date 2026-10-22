"""Typed errors raised by LLM providers.

These let callers distinguish *expected, non-fatal* provider conditions
(such as a rate limit or quota rejection) from genuine failures.
"""

from __future__ import annotations

import math
import re
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

#: Prefix that marks a rate-limit message in plain-text channels (agent
#: results, final answers) so that clients can render it as a non-fatal
#: notice.  Format: ``[rate_limited retry_after=<seconds>] <message>``
#: (the ``retry_after`` attribute is omitted when unknown).
RATE_LIMIT_MARKER = "rate_limited"

_MARKER_RE = re.compile(
    r"^\[" + RATE_LIMIT_MARKER + r"(?:\s+retry_after=(?P<retry>\d+(?:\.\d+)?))?\]\s*(?P<msg>.*)$",
    re.DOTALL,
)


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

    def __init__(self, detail: Optional[str] = None, retry_after: Optional[float] = None) -> None:
        self.detail = detail or "The model endpoint is rate limiting requests."
        self.retry_after = retry_after
        super().__init__(self.detail)

    def user_message(self) -> str:
        msg = f"Rate limit reached: {self.detail}"
        if self.retry_after is not None:
            msg += f" Please retry in {format_delay(self.retry_after)}."
        return msg

    def __str__(self) -> str:
        attr = ""
        if self.retry_after is not None:
            attr = f" retry_after={self.retry_after:g}"
        return f"[{RATE_LIMIT_MARKER}{attr}] {self.user_message()}"


def format_delay(seconds: float) -> str:
    seconds = max(0, math.ceil(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes}min" if rest == 0 else f"{minutes}min {rest}s"


def parse_retry_after(value: Optional[str]) -> Optional[float]:
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
        when = when.replace(tzinfo=timezone.utc)
    return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())


def extract_error_detail(body: Any) -> Optional[str]:
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
    headers: Optional[Mapping[str, str]], body: Any
) -> LLMRateLimitError:
    retry = parse_retry_after(headers.get("retry-after") if headers else None)
    return LLMRateLimitError(extract_error_detail(body), retry)


def parse_rate_limit_marker(text: str) -> Optional[tuple[str, Optional[float]]]:
    """Inverse of ``str(LLMRateLimitError)``: return ``(message, retry_after)``."""
    m = _MARKER_RE.match(text.strip())
    if not m:
        return None
    retry = m.group("retry")
    return m.group("msg"), float(retry) if retry is not None else None
