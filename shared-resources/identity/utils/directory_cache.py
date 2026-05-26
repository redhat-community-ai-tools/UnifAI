"""
Redis-backed cache for directory lookup responses.

Caches lightweight JSON payloads for short TTL to reduce repeated LDAP calls
and provide graceful fallback during transient LDAP errors.
"""
import hashlib
import json
import logging
from typing import Any, Optional

from global_utils.redis.redis_kv_store import RedisKVStore

logger = logging.getLogger(__name__)

KEY_PREFIX = "unifai:directory:"
DEFAULT_TTL_SECONDS = 300


class DirectoryCache:
    """Cache wrapper for directory search/get responses."""

    def __init__(self, store: RedisKVStore, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self._store = store
        self._ttl_seconds = ttl_seconds

    def get_json(self, key: str) -> Optional[Any]:
        try:
            raw = self._store.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.exception("Failed to read directory cache key=%s", key)
            return None

    def set_json(self, key: str, value: Any) -> None:
        try:
            self._store.set(key, json.dumps(value), ttl_seconds=self._ttl_seconds)
        except Exception:
            logger.exception("Failed to write directory cache key=%s", key)

    @staticmethod
    def key_for_search(scope: str, query: str, limit: int, user_token: Optional[str]) -> str:
        token_fingerprint = DirectoryCache._token_fingerprint(user_token)
        return f"{KEY_PREFIX}{scope}:q={query.strip().lower()}:l={limit}:t={token_fingerprint}"

    @staticmethod
    def key_for_group(group_id: str, user_token: Optional[str]) -> str:
        token_fingerprint = DirectoryCache._token_fingerprint(user_token)
        return f"{KEY_PREFIX}group:id={group_id.strip().lower()}:t={token_fingerprint}"

    @staticmethod
    def _token_fingerprint(user_token: Optional[str]) -> str:
        if not user_token:
            return "anon"
        return hashlib.sha256(user_token.encode("utf-8")).hexdigest()[:12]
