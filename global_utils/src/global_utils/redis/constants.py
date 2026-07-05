"""
Central registry of Redis key prefixes and key-builder helpers.

Every module that writes or reads Redis keys should import its prefix / builder
from here so the namespace scheme is defined in one place.

All identity-related keys live under the ``identity:`` namespace:

    identity:session:{session_id}     — server-side session hash
    identity:user_groups:{username}   — LDAP/Rover group cache (JSON)
    identity:user_teams:{username}    — team membership cache (JSON)
    identity:directory:...            — directory search/lookup cache (JSON)
"""

IDENTITY_SESSION_PREFIX = "identity:session"
IDENTITY_USER_GROUPS_PREFIX = "identity:user_groups"
IDENTITY_USER_TEAMS_PREFIX = "identity:user_teams"
IDENTITY_DIRECTORY_PREFIX = "identity:directory"


def identity_session_key(session_id: str) -> str:
    """Build the Redis key for an identity server-session hash."""
    return f"{IDENTITY_SESSION_PREFIX}:{session_id}"
