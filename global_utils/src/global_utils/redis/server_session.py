"""
Load the identity service server session from Redis (no Flask — apps wire ``session_id`` and ``g`` themselves).

Use with :class:`global_utils.redis.RedisKVStore` (or any object with the same ``hget``/HGETALL
shape as the identity service hash).
"""

from __future__ import annotations

from typing import Any

from global_utils.redis.constants import identity_session_key
from global_utils.redis.session_model import UserSessionData


def get_identity_session(redis_store: Any, session_id: str | None) -> UserSessionData | None:
    """
    Read the Redis hash for ``session_id`` and parse it as :class:`UserSessionData`.

    Returns ``None`` if the id is missing, or Redis has no data for the key.
    """
    if not session_id or not str(session_id).strip():
        return None
    raw = redis_store.hget(identity_session_key(str(session_id)))
    if not raw:
        return None
    return UserSessionData.from_redis_hash(raw)


def get_identity_username(redis_store: Any, session_id: str | None) -> str | None:
    """
    Load the server session and return ``username`` if present, else ``None``.

    Calls :func:`get_identity_session` (one Redis read); does not add extra round-trips.
    """
    data = get_identity_session(redis_store, session_id)
    if data is None or data.username is None:
        return None
    name = str(data.username).strip()
    return name or None
