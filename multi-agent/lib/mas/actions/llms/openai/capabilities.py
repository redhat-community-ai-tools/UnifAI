"""
OpenAI model capabilities — loading and lookup.

Two concerns live here:

1. **Loading** (``load_capabilities``) — reads the ``openai_model_capabilities``
   section from an injected ``AdminConfigReaderPort``, with a 30-second TTL
   cache so the UI gets fresh data without hammering the database on every
   request.

2. **Lookup** (``find_model_capabilities``) — pure prefix-matching function
   that finds the best entry for a given model name using the longest-prefix
   rule (``"gpt-5.6-sol"`` beats ``"gpt-5"``).

Both functions are used exclusively by the ``openai.get_models`` and
``openai.get_reasoning_levels`` actions to populate UI dropdowns.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

from mas.core.identity.ports import AdminConfigReaderPort

logger = logging.getLogger(__name__)

_ADMIN_CONFIG_SECTION = "openai_model_capabilities"
_CAPABILITIES_KEY = "capabilities"
_CACHE_TTL_SECONDS: float = 30.0

# ── TTL cache ─────────────────────────────────────────────────────────────────

_cached_map: Optional[Dict[str, Dict[str, Any]]] = None
_cached_at: float = 0.0


def load_capabilities(reader: AdminConfigReaderPort) -> Dict[str, Dict[str, Any]]:
    """Return the capabilities map from admin config, TTL-cached for 30 s.

    Args:
        reader: Port that reads from the centralized admin config store.

    Returns an empty dict when the section is absent or the reader fails,
    so callers degrade gracefully.
    """
    global _cached_map, _cached_at
    now = time.monotonic()
    if _cached_map is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_map

    section = reader.get_section(_ADMIN_CONFIG_SECTION)
    if section is not None:
        caps = section.get(_CAPABILITIES_KEY)
        if isinstance(caps, dict) and caps:
            _cached_map = caps
            _cached_at = now
            return _cached_map

    if _cached_map is not None:
        logger.debug("Could not refresh OpenAI model capabilities; serving stale cache.")
        return _cached_map

    logger.warning(
        "OpenAI model capabilities not found in admin config (section=%s).",
        _ADMIN_CONFIG_SECTION,
    )
    return {}


# ── Pure lookup ───────────────────────────────────────────────────────────────

def find_model_capabilities(
    caps: Dict[str, Dict[str, Any]],
    model_name: str,
) -> Optional[Dict[str, Any]]:
    """Return the capability entry for *model_name*, or ``None`` if not found.

    Uses the longest-prefix rule: ``"gpt-5.6-sol"`` beats ``"gpt-5"``.

    Args:
        caps: The full capabilities map (from ``load_capabilities()``).
        model_name: Full model ID, e.g. ``"gpt-5.6-sol"``.
    """
    best_prefix = ""
    best_cap = None
    for prefix, cap in caps.items():
        if model_name.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_cap = cap
    return best_cap
