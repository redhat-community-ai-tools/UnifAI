"""Sanitize LLM function/tool names at the API boundary.

Different LLM providers impose different character restrictions on
function names.  Two presets are provided:

* **ALLOW_HYPHEN** – ``[a-zA-Z0-9_-]``  (e.g. OpenAI)
* **STRICT** – ``[a-zA-Z0-9_]``  (e.g. Google GenAI / Gemini)

Domain tool names (e.g. ``time.get_current_time``) are left unchanged in
the internal registry; this map only exists so the converter can emit a
legal name and restore the original when the model returns a tool call.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

# ---- Character-set presets ----------------------------------------------
# Each pair consists of:
#   *_UNSAFE  – matches characters that must be replaced
#   *_SAFE    – fully matches a name that is already valid

ALLOW_HYPHEN_UNSAFE = re.compile(r"[^a-zA-Z0-9_-]")
ALLOW_HYPHEN_SAFE = re.compile(r"^[a-zA-Z0-9_-]+$")

STRICT_UNSAFE = re.compile(r"[^a-zA-Z0-9_]")
STRICT_SAFE = re.compile(r"^[a-zA-Z0-9_]+$")


def sanitize_tool_name(
    name: str,
    unsafe_re: re.Pattern[str] = ALLOW_HYPHEN_UNSAFE,
) -> str:
    """Replace characters not matching the provider's allowed set with ``_``."""
    return unsafe_re.sub("_", name) or "tool"


class ToolNameSanitizer:
    """Bidirectional map between domain tool names and provider-safe names.

    Collisions get a numeric suffix: ``foo_bar``, ``foo_bar_2``, …
    Already-valid names are registered first so a real ``foo_bar`` tool
    keeps that name and a dotted ``foo.bar`` becomes ``foo_bar_2``.

    Parameters
    ----------
    names:
        Optional iterable of domain names to register eagerly.
    unsafe_re:
        Regex matching *disallowed* characters.  Defaults to
        ``ALLOW_HYPHEN_UNSAFE`` (``[^a-zA-Z0-9_-]``).
    safe_re:
        Regex that *fully matches* a legal name.  Defaults to
        ``ALLOW_HYPHEN_SAFE`` (``^[a-zA-Z0-9_-]+$``).
    """

    def __init__(
        self,
        names: Optional[Iterable[str]] = None,
        *,
        unsafe_re: re.Pattern[str] = ALLOW_HYPHEN_UNSAFE,
        safe_re: re.Pattern[str] = ALLOW_HYPHEN_SAFE,
    ) -> None:
        self._unsafe_re = unsafe_re
        self._safe_re = safe_re
        self._to_provider: Dict[str, str] = {}
        self._to_domain: Dict[str, str] = {}
        if names is not None:
            self.register_all(names)

    # -- bulk registration ------------------------------------------------

    def register_all(self, names: Iterable[str]) -> None:
        ordered = list(names)
        for name in ordered:
            if self._safe_re.fullmatch(name):
                self.register(name)
        for name in ordered:
            if not self._safe_re.fullmatch(name):
                self.register(name)

    # -- single registration / lookup -------------------------------------

    def register(self, original: str) -> str:
        if original in self._to_provider:
            return self._to_provider[original]

        candidate = sanitize_tool_name(original, self._unsafe_re)
        safe = candidate
        suffix = 2
        while safe in self._to_domain and self._to_domain[safe] != original:
            safe = f"{candidate}_{suffix}"
            suffix += 1

        self._to_provider[original] = safe
        self._to_domain[safe] = original
        return safe

    def to_provider(self, name: str) -> str:
        """Map a domain name to the provider-safe name."""
        if name in self._to_provider:
            return self._to_provider[name]
        if name in self._to_domain:
            return name
        return self.register(name)

    def to_domain(self, name: str) -> str:
        """Map a provider-safe name back to the original domain name."""
        return self._to_domain.get(name, name)
