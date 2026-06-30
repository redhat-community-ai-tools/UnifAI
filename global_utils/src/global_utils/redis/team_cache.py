"""
Redis-backed cache for user **team** memberships (UnifAI internal teams).

Follows the same pattern as
``shared-resources/identity/utils/user_groups_cache.py`` (JSON blob under
a per-user key with a TTL), but lives in ``global_utils`` so any Flask
service can leverage it via ``IdentityClient``.

Keys: ``identity:user_teams:{username}``
Value: JSON-encoded ``list[str]`` of team IDs.
"""
import json
import logging
from typing import List, Optional

from global_utils.redis.constants import IDENTITY_USER_TEAMS_PREFIX
from global_utils.redis.redis_kv_store import RedisKVStore

logger = logging.getLogger(__name__)

_DEFAULT_TTL = 300  # 5 minutes
KEY_PREFIX = f"{IDENTITY_USER_TEAMS_PREFIX}:"


class TeamMembershipCache:
    """Thin Redis wrapper for user -> team-ID lists."""

    def __init__(self, store: RedisKVStore, ttl: int = _DEFAULT_TTL):
        self._store = store
        self._ttl = ttl

    def get_team_ids(self, username: str) -> Optional[List[str]]:
        """Return cached team IDs or ``None`` on a miss / error."""
        try:
            raw = self._store.get(self._key(username))
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            logger.exception("Failed to read team cache for %s", username)
            return None

    def set_team_ids(self, username: str, team_ids: List[str]) -> None:
        """Write team IDs with TTL."""
        try:
            self._store.set(self._key(username), json.dumps(team_ids), ttl_seconds=self._ttl)
            logger.debug("Cached %d teams for %s (ttl=%ds)", len(team_ids), username, self._ttl)
        except Exception:
            logger.exception("Failed to cache teams for %s", username)

    def invalidate(self, username: str) -> None:
        """Drop the cache entry so the next read hits the source of truth."""
        try:
            self._store.delete(self._key(username))
        except Exception:
            logger.exception("Failed to invalidate team cache for %s", username)

    def _key(self, username: str) -> str:
        return f"{KEY_PREFIX}{username}"
