"""Abstract token repository interface (port)."""
from abc import ABC, abstractmethod
from typing import List, Optional

from tokens.models import ApiToken, TokenCreateResult, TokenUserData


class TokenRepository(ABC):

    @abstractmethod
    def create(self, user_id: str, name: str, user_data: TokenUserData,
               ttl_seconds: int = 36000) -> TokenCreateResult:
        """Create a new API token. Returns the plaintext token once."""

    @abstractmethod
    def validate(self, token: str) -> Optional[TokenUserData]:
        """Validate a token. Returns user data if valid, None otherwise."""

    @abstractmethod
    def list_by_user(self, user_id: str) -> List[ApiToken]:
        """List active (non-revoked) tokens for a user."""

    @abstractmethod
    def revoke(self, user_id: str, name: str) -> bool:
        """Revoke a token by name. Returns True if found and revoked."""

    @abstractmethod
    def revoke_all(self, user_id: str) -> int:
        """Revoke all tokens for a user. Returns count revoked."""
