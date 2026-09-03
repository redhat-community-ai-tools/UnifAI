"""Sanitize OpenAI function names at the API boundary.

OpenAI requires function names matching ``^[a-zA-Z0-9_-]+$``. Domain
tool names (e.g. ``time.get_current_time``) are left unchanged in the
registry; this map only exists so the converter can emit a legal name
and restore the original when the model returns a tool call.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

_UNSAFE_CHARS = re.compile(r"[^a-zA-Z0-9_-]")
_SAFE_NAME = re.compile(r"^[a-zA-Z0-9_-]+$")


def sanitize_tool_name(name: str) -> str:
    """Replace characters outside ``[a-zA-Z0-9_-]`` with ``_``."""
    return _UNSAFE_CHARS.sub("_", name) or "tool"


class ToolNameSanitizer:
    """Bidirectional map between domain tool names and OpenAI-safe names.

    Collisions get a numeric suffix: ``foo_bar``, ``foo_bar_2``, …
    Already-valid names are registered first so a real ``foo_bar`` tool
    keeps that name and a dotted ``foo.bar`` becomes ``foo_bar_2``.
    """

    def __init__(self, names: Optional[Iterable[str]] = None) -> None:
        self._to_provider: dict[str, str] = {}
        self._to_domain: dict[str, str] = {}
        if names is not None:
            self.register_all(names)

    def register_all(self, names: Iterable[str]) -> None:
        ordered = list(names)
        for name in ordered:
            if _SAFE_NAME.fullmatch(name):
                self.register(name)
        for name in ordered:
            if not _SAFE_NAME.fullmatch(name):
                self.register(name)

    def register(self, original: str) -> str:
        if original in self._to_provider:
            return self._to_provider[original]

        candidate = sanitize_tool_name(original)
        safe = candidate
        suffix = 2
        while safe in self._to_domain and self._to_domain[safe] != original:
            safe = f"{candidate}_{suffix}"
            suffix += 1

        self._to_provider[original] = safe
        self._to_domain[safe] = original
        return safe

    def to_provider(self, name: str) -> str:
        if name in self._to_provider:
            return self._to_provider[name]
        if name in self._to_domain:
            return name
        return self.register(name)

    def to_domain(self, name: str) -> str:
        return self._to_domain.get(name, name)
