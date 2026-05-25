"""
Identity directory adapter — delegates to the shared IdentityClient.

Preserves the ``DirectoryProvider`` port and lightweight Pydantic models so
existing callers (shares endpoint, etc.) keep working unchanged.
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Optional

from pydantic import BaseModel, Field

from global_utils.identity_client import IdentityClient

logger = logging.getLogger(__name__)


# ── lightweight directory models ──────────────────────────────────────

class DirectoryUser(BaseModel):
    user_id: str
    username: str
    display_name: str
    email: str = ""
    title: str = ""


class DirectoryGroup(BaseModel):
    group_id: str
    name: str
    description: str = ""
    members: List[str] = Field(default_factory=list)


class DirectoryProvider(ABC):
    """Minimal port for an external user/group directory."""

    def set_user_token(self, token: str) -> None:
        pass

    @abstractmethod
    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]: ...

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[DirectoryUser]: ...

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        return []

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        return None


# ── Identity HTTP client ──────────────────────────────────────────────

class IdentityDirectoryClient(DirectoryProvider):
    """Delegates directory lookups to a shared :class:`IdentityClient`."""

    def __init__(self, identity_client: IdentityClient, timeout: int = 10):
        self._client = identity_client
        self._timeout = timeout
        self._user_token: Optional[str] = None
        logger.info(
            "Identity directory client: %s (delegating to IdentityClient)",
            self._client._base,
        )

    def set_user_token(self, token: str) -> None:
        self._user_token = token

    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        try:
            raw = self._client.search_directory(
                query, limit=limit, token=self._user_token,
            )
            return [DirectoryUser(**u) for u in raw]
        except Exception:
            logger.exception("SSO directory search_users failed")
            return []

    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        try:
            raw = self._client.get_user(user_id, token=self._user_token)
            if raw is None:
                return None
            return DirectoryUser(**raw)
        except Exception:
            logger.exception("SSO directory get_user failed")
            return None

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        try:
            raw = self._client.search_groups(query, limit=limit, token=self._user_token)
            return [DirectoryGroup(**g) for g in raw]
        except Exception:
            logger.exception("SSO directory search_groups failed")
            return []

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        try:
            raw = self._client.get_group(group_id, token=self._user_token)
            if raw is None:
                return None
            return DirectoryGroup(**raw)
        except Exception:
            logger.exception("SSO directory get_group failed")
            return []
