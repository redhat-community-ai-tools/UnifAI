"""
Contract for the Redis hash document created by the identity service after Keycloak login.

The identity service stores this under the Flask ``session_id`` value as a Redis hash
(see ``hset`` / ``hgetall`` on :class:`global_utils.redis.RedisKVStore`).

All fields are optional on parse so partial or legacy rows do not break validation;
use :meth:`UserSessionData.has_auth_credentials` for a stricter check aligned
with identity's ``is_authenticated`` (username + access_token present).
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserSessionData(BaseModel):
    """
    Server-side session payload (Redis hash) for identity flows.

    Written on OAuth callback; updated on token refresh. Field names match
    ``shared-resources/identity`` ``AuthManager`` / Keycloak userinfo and token
    objects.
    """

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    username: str | None = None
    email: str | None = None
    name: str | None = None
    sub: str | None = None

    session_created_at: float | None = Field(
        default=None,
        description="Unix timestamp when the app session was created.",
    )
    session_expires_at: float | None = Field(
        default=None,
        description="Unix timestamp when the app session must end (e.g. 10h after login).",
    )
    token_expires_at: float | int | None = Field(
        default=None,
        description="OIDC access token expiry (from provider), unix seconds.",
    )

    access_token: str | None = None
    refresh_token: str | None = None

    @classmethod
    def from_redis_hash(cls, data: Mapping[str, Any] | None) -> UserSessionData | None:
        """
        Build a model from :meth:`global_utils.redis.RedisKVStore.hget` / Redis HGETALL.

        Normalizes string numerics from Redis; ignores unknown keys.
        """
        if not data:
            return None
        flat: dict[str, Any] = {}
        for raw_key, raw_value in data.items():
            key = raw_key.decode("utf-8") if isinstance(raw_key, bytes) else str(raw_key)
            value: Any
            if isinstance(raw_value, bytes):
                value = raw_value.decode("utf-8")
            else:
                value = raw_value
            if key in {
                "session_created_at",
                "session_expires_at",
                "token_expires_at",
            } and value not in (None, ""):
                if isinstance(value, str):
                    try:
                        value = float(value)
                    except ValueError:
                        pass
            flat[key] = value
        return cls.model_validate(flat)

    def has_auth_credentials(self) -> bool:
        """True when both username and access_token are set (typical for authenticated)."""
        return bool(self.username and self.access_token)

    def is_session_expired(self) -> bool:
        """True when ``session_expires_at`` is missing or in the past."""
        if self.session_expires_at is None:
            return True  # ponytail: fail closed — matches identity service semantics
        return datetime.now().timestamp() >= self.session_expires_at
