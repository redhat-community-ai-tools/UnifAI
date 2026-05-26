"""
Redis-backed cache for user ROVER/directory group memberships.

Uses :class:`global_utils.redis.RedisKVStore` (same Redis connection pattern as
identity sessions). On login, groups are cached with a TTL; reads avoid
repeated LDAP calls.
"""
import json
import logging
from typing import List, Optional

from global_utils.redis.redis_kv_store import RedisKVStore

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 3600  # 1 hour
KEY_PREFIX = "unifai:user_groups:"


class UserGroupsCache:
    """Thin wrapper around :class:`RedisKVStore` for user-group JSON blobs."""

    def __init__(self, store: RedisKVStore, ttl: int = _DEFAULT_TTL):
        self._store = store
        self._ttl = ttl

    def set_groups(self, username: str, groups: List[dict]) -> None:
        key = self._key(username)
        try:
            self._store.set(key, json.dumps(groups), ttl_seconds=self._ttl)
            logger.debug("Cached %d groups for %s (ttl=%ds)", len(groups), username, self._ttl)
        except Exception:
            logger.exception("Failed to cache groups for %s", username)

    def get_groups(self, username: str) -> Optional[List[dict]]:
        key = self._key(username)
        try:
            raw = self._store.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.exception("Failed to read cached groups for %s", username)
            return None

    def invalidate(self, username: str) -> None:
        try:
            self._store.delete(self._key(username))
        except Exception:
            logger.exception("Failed to invalidate group cache for %s", username)

    def _key(self, username: str) -> str:
        return f"{KEY_PREFIX}{username}"
