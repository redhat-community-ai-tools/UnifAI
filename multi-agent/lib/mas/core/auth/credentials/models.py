"""
Auth-layer models — scheme-agnostic.

All credential, token, and client-config models live here.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


def _is_expired(expires_at: Optional[datetime], buffer_seconds: int = 60) -> bool:
    """Shared timezone-aware expiry check."""
    if expires_at is None:
        return False
    exp = expires_at if expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    return exp <= datetime.now(timezone.utc) + timedelta(seconds=buffer_seconds)


class TokenStatus(str, Enum):
    ACTIVE = "active"
    REFRESH_FAILED = "refresh_failed"
    REVOKED = "revoked"


class TokenSet(BaseModel):
    """Fresh credential set produced by any auth scheme."""
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scope: Optional[str] = None

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        return _is_expired(self.expires_at, buffer_seconds)


class StoredCredential(BaseModel):
    """
    Persisted per-user, per-server credential.

    Lookup key: ``(user_id, server_identifier)``.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: str
    server_identifier: str = Field(
        default="",
        description="Auth server issuer URL (e.g. https://accounts.google.com)",
    )
    access_token: str
    refresh_token: Optional[str] = None
    token_type: str = "Bearer"
    expires_at: Optional[datetime] = None
    scopes: List[str] = Field(default_factory=list)
    status: TokenStatus = TokenStatus.ACTIVE
    scheme_type: str = "oauth2"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def is_valid(self, buffer_seconds: int = 60) -> bool:
        if self.status != TokenStatus.ACTIVE:
            return False
        return not _is_expired(self.expires_at, buffer_seconds)


class ClientConfig(BaseModel):
    """Client config for an auth server (OAuth app registration, etc.)."""
    client_id: str
    client_secret: Optional[str] = None
    authorization_endpoint: str = ""
    token_endpoint: str = ""
    token_endpoint_auth_method: str = "client_secret_post"
    scopes: List[str] = Field(default_factory=list)
    resource_uri: Optional[str] = None
    extra_authorize_params: Dict[str, str] = Field(default_factory=dict)
    protocol_type: str = "oauth2"
    server_identifier: str = ""


class RecoveryResult(BaseModel):
    """Outcome of an attempt_recovery call."""
    model_config = {"frozen": True}

    recovered: bool
    should_retry: bool
    reason: str
    new_token_set: Optional[TokenSet] = None
