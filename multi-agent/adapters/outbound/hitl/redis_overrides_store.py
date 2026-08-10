"""
Redis-backed ``OverridesStore`` — shared live state for auto-approval rules.

Enables cross-process rule sync between the Flask API (which writes rules)
and the Temporal worker (which reads them during tool-call gating).

Keys:   ``hitl:overrides:{session_id}``
Value:  JSON-serialised ``ApprovalOverrides``
TTL:    Configurable (defaults to 24 h) — acts as a safety net; explicit
        ``remove()`` is called on run completion.
"""
import json
import logging

from redis import ConnectionPool, Redis

from mas.core.hitl.models import ApprovalOverrides
from mas.core.hitl.ports import OverridesStore

logger = logging.getLogger(__name__)

_PREFIX = "hitl:overrides:"
_DEFAULT_TTL = 86_400  # 24 hours


class RedisOverridesStore(OverridesStore):

    def __init__(self, redis_url: str, ttl: int = _DEFAULT_TTL) -> None:
        self._pool = ConnectionPool.from_url(redis_url, socket_timeout=30)
        self._ttl = ttl

    def _redis(self) -> Redis:
        return Redis(connection_pool=self._pool)

    def load(self, session_id: str) -> ApprovalOverrides:
        raw = self._redis().get(f"{_PREFIX}{session_id}")
        if raw is None:
            return ApprovalOverrides()
        try:
            return ApprovalOverrides.from_dict(json.loads(raw))
        except (json.JSONDecodeError, TypeError, KeyError):
            logger.warning("Corrupt overrides in Redis for session %s — returning empty", session_id)
            return ApprovalOverrides()

    def save(self, session_id: str, overrides: ApprovalOverrides) -> None:
        key = f"{_PREFIX}{session_id}"
        self._redis().setex(key, self._ttl, json.dumps(overrides.to_dict()))
        logger.debug("Overrides saved to Redis: session=%s, overrides=%s", session_id, overrides.to_dict())

    def remove(self, session_id: str) -> None:
        self._redis().delete(f"{_PREFIX}{session_id}")
        logger.debug("Overrides removed from Redis: session=%s", session_id)
