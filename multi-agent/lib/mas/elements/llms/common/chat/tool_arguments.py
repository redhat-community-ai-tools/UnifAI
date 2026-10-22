"""Tolerant parsing of tool-call argument strings assembled from a stream."""

from __future__ import annotations

import json
from typing import Any, Dict, List

ARGUMENTS_ERROR_KEY = "_arguments_error"


def is_complete_json(raw: str) -> bool:
    """True when *raw* is one complete JSON document."""
    try:
        json.loads(raw)
    except ValueError:
        return False
    return True


def split_json_objects(raw: str) -> List[Any]:
    """Split a string of back-to-back JSON documents (``{..}{..}``).

    Returns an empty list when the string is not made solely of JSON documents.
    """
    decoder = json.JSONDecoder()
    out: List[Any] = []
    pos, n = 0, len(raw)
    while pos < n:
        while pos < n and raw[pos].isspace():
            pos += 1
        if pos >= n:
            break
        try:
            obj, pos = decoder.raw_decode(raw, pos)
        except ValueError:
            return []
        out.append(obj)
    return out


def parse_tool_arguments(raw: str) -> Dict[str, Any]:
    """Parse *raw* into an argument dict without ever raising.

    Empty input gives ``{}``.  Invalid or non-object JSON gives a dict holding
    a single ``_arguments_error`` entry so the failure surfaces as a tool-call
    error instead of an unhandled exception in the agent loop.
    """
    if not raw or not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except ValueError as exc:
        return {ARGUMENTS_ERROR_KEY: f"tool call arguments are not valid JSON ({exc}): {raw[:200]!r}"}
    if not isinstance(value, dict):
        return {ARGUMENTS_ERROR_KEY: f"tool call arguments must be a JSON object, got {type(value).__name__}"}
    return value
