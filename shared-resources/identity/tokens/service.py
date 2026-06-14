"""
Token service — application use-case boundary for API token lifecycle.

Owns business rules (duplicate check, validation, revocation logic).
Delegates persistence to the TokenRepository port.
"""
from typing import List, Optional

from tokens.models import ApiToken, TokenCreateResult, TokenUserData
from tokens.repository.repository import TokenRepository


class TokenAlreadyExistsError(ValueError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Token with name '{name}' already exists")


class TokenNotFoundError(KeyError):
    def __init__(self, name: str):
        self.name = name
        super().__init__(f"Token '{name}' not found or already revoked")


class TokenService:

    def __init__(self, repository: TokenRepository):
        self._repo = repository

    def create(self, user_id: str, name: str, user_data: TokenUserData,
               ttl_seconds: int = 7776000) -> TokenCreateResult:
        existing = self._repo.list_by_user(user_id)
        if any(t.name == name for t in existing):
            raise TokenAlreadyExistsError(name)
        return self._repo.create(user_id=user_id, name=name,
                                 user_data=user_data, ttl_seconds=ttl_seconds)

    def list(self, user_id: str) -> List[ApiToken]:
        return self._repo.list_by_user(user_id)

    def revoke(self, user_id: str, name: str) -> None:
        revoked = self._repo.revoke(user_id=user_id, name=name)
        if not revoked:
            raise TokenNotFoundError(name)

    def revoke_all(self, user_id: str) -> int:
        return self._repo.revoke_all(user_id)

    def validate(self, token: str) -> Optional[TokenUserData]:
        """Validate a token. Returns user data if valid, None otherwise."""
        return self._repo.validate(token)
