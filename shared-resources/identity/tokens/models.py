"""Domain model for API tokens."""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


TOKEN_PREFIX = "unifai_t_"


class TokenUserData(BaseModel):
    """Snapshot of user data captured at token creation time."""
    username: str
    email: str = ""
    display_name: str = ""
    sub: str = ""


class ApiToken(BaseModel):
    """Represents a stored API token (without the plaintext secret)."""
    token_hash: str
    user_id: str
    name: str
    user_data: TokenUserData
    created_at: datetime
    expires_at: datetime
    last_used_at: Optional[datetime] = None
    revoked: bool = False

    def is_expired(self) -> bool:
        return self.expires_at < datetime.now(timezone.utc)

    def is_valid(self) -> bool:
        return not self.revoked and not self.is_expired()


class TokenCreateResult(BaseModel):
    """Returned to the user once on creation — contains the plaintext token."""
    token: str
    name: str
    expires_at: str
    expires_in: int = Field(description="Token lifetime in seconds")
