"""
Central registry of Redis key prefixes, key-builder helpers, and shared
auth constants.

Every module that writes or reads Redis keys should import its prefix / builder
from here so the namespace scheme is defined in one place.
"""

IDENTITY_SESSION_PREFIX = "identity:session"

SESSION_COOKIE_NAME = "unifai_session_id"


def identity_session_key(session_id: str) -> str:
    """Build the Redis key for an identity server-session hash."""
    return f"{IDENTITY_SESSION_PREFIX}:{session_id}"
