"""
Model capability registry for the OpenAI Responses API provider.

The capabilities dict maps model-name **prefixes** to their supported
reasoning-effort levels.  More specific prefixes take precedence, so
``"gpt-5.6-sol"`` overrides the generic ``"gpt-5"`` entry.

**Purpose**

This module is used exclusively by the ``openai.get_models`` and
``openai.get_reasoning_levels`` actions to populate UI dropdowns.
It is **not** used at session runtime — if the user saves a resource
without selecting a reasoning effort, OpenAI's server-side default
is applied automatically.

**Reader**

A lazy ``MongoAdminConfigReader`` singleton is created on first access
using the same env vars that the rest of the multi-agent service reads
(``mongodb_ip``, ``mongodb_port``, ``admin_config_db``). No dependency
injection is required.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ADMIN_CONFIG_SECTION = "openai_model_capabilities"
_CAPABILITIES_KEY = "capabilities"
_CACHE_TTL_SECONDS: float = 30.0

# ── Lazy reader singleton ─────────────────────────────────────────────────────

_reader = None


def _get_reader():
    """Return a lazily-initialised MongoAdminConfigReader singleton."""
    global _reader
    if _reader is None:
        from adapters.outbound.mongo.admin_config_reader import MongoAdminConfigReader
        _reader = MongoAdminConfigReader(
            mongodb_ip=os.environ.get("mongodb_ip", "0.0.0.0"),
            mongodb_port=os.environ.get("mongodb_port", "27017"),
            db_name=os.environ.get("admin_config_db", "config"),
        )
    return _reader


# ── Module-level TTL cache ────────────────────────────────────────────────────

_cached_map: Optional[Dict[str, Dict[str, Any]]] = None
_cached_at: float = 0.0


def get_capabilities_map() -> Dict[str, Dict[str, Any]]:
    """Return the live capabilities map, TTL-cached for 30 s.

    Returns an empty dict when the section is absent or MongoDB is
    unreachable, so callers degrade gracefully.
    """
    global _cached_map, _cached_at
    now = time.monotonic()
    if _cached_map is not None and (now - _cached_at) < _CACHE_TTL_SECONDS:
        return _cached_map

    section = _get_reader().get_section(_ADMIN_CONFIG_SECTION)
    if section is not None:
        caps = section.get(_CAPABILITIES_KEY)
        if isinstance(caps, dict) and caps:
            _cached_map = caps
            _cached_at = now
            return _cached_map

    if _cached_map is not None:
        logger.debug(
            "Could not refresh OpenAI model capabilities; serving stale cache."
        )
        return _cached_map

    logger.warning(
        "OpenAI model capabilities not found in admin config (section=%s).",
        _ADMIN_CONFIG_SECTION,
    )
    return {}


def get_model_capabilities(
    model_name: str,
    capabilities: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Return capabilities for *model_name*, or ``None`` if not found.

    Matching uses the longest-prefix rule so that ``"gpt-5.6-sol"`` takes
    precedence over the more generic ``"gpt-5"`` entry.

    Args:
        model_name: Full model ID, e.g. ``"gpt-5.6-sol"``.
        capabilities: Pre-fetched capabilities map; fetched automatically when omitted.
    """
    caps = capabilities if capabilities is not None else get_capabilities_map()
    best_prefix = ""
    best_cap = None
    for prefix, cap in caps.items():
        if model_name.startswith(prefix) and len(prefix) > len(best_prefix):
            best_prefix = prefix
            best_cap = cap
    return best_cap
