"""Sanitize LLM tool names at the API boundary.

OpenAI requires function names matching ``^[a-zA-Z0-9_-]{1,64}$``.
Domain tool names (e.g. ``time.get_current_time``) contain dots that
must be replaced before sending to the provider and restored when
parsing the response.
"""

from __future__ import annotations

from typing import Dict, Iterable, Tuple

_MAX_NAME_LENGTH = 64


def sanitize_tool_name(name: str) -> str:
    """Replace dots with underscores, truncate to 64 chars."""
    safe = name.replace(".", "_")
    return safe[:_MAX_NAME_LENGTH]


def build_name_maps(
    names: Iterable[str],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    """Build forward (domain → safe) and reverse (safe → domain) dicts."""
    forward: Dict[str, str] = {}
    reverse: Dict[str, str] = {}
    for name in names:
        safe = sanitize_tool_name(name)
        forward[name] = safe
        reverse[safe] = name
    return forward, reverse
