"""Shared Redis helpers (client factory and KV store adapter)."""

from global_utils.redis.client import build_redis_client
from global_utils.redis.constants import (
    IDENTITY_DIRECTORY_PREFIX,
    IDENTITY_SESSION_PREFIX,
    IDENTITY_USER_GROUPS_PREFIX,
    IDENTITY_USER_TEAMS_PREFIX,
    identity_session_key,
)
from global_utils.redis.redis_kv_store import RedisKVStore
from global_utils.redis.server_session import get_identity_session, get_identity_username
from global_utils.redis.session_model import UserSessionData
from global_utils.redis.team_cache import TeamMembershipCache

__all__ = [
    "build_redis_client",
    "IDENTITY_DIRECTORY_PREFIX",
    "IDENTITY_SESSION_PREFIX",
    "IDENTITY_USER_GROUPS_PREFIX",
    "IDENTITY_USER_TEAMS_PREFIX",
    "identity_session_key",
    "RedisKVStore",
    "get_identity_session",
    "get_identity_username",
    "TeamMembershipCache",
    "UserSessionData",
]
