"""
Abstract directory provider interface.

Defines the contract for any external system that owns user and group
identity data (corporate LDAP, SSO user-store, Azure AD, etc.).

Domain code depends only on this port.  Concrete adapters live under
the same package and are selected in each service's composition root.
"""
from abc import ABC, abstractmethod
from typing import List, Optional

from directory.models import DirectoryUser, DirectoryGroup


class DirectoryProvider(ABC):
    """Port for an external user/group directory."""

    def set_user_token(self, token: str) -> None:
        """Supply the calling user's access token for providers that
        authenticate on behalf of the logged-in user rather than using
        service-level credentials.  Default implementation is a no-op;
        adapters that need it override this."""

    # ── users ──────────────────────────────────────────────────────────

    @abstractmethod
    def search_users(self, query: str, limit: int = 20) -> List[DirectoryUser]:
        """Free-text search over the directory's user base."""

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[DirectoryUser]:
        """Look up a single user by their unique directory identifier."""

    # ── groups ─────────────────────────────────────────────────────────

    def search_groups(self, query: str, limit: int = 20) -> List[DirectoryGroup]:
        """Free-text search over the directory's groups."""
        return []

    def get_group(self, group_id: str) -> Optional[DirectoryGroup]:
        """Look up a single group by its unique directory identifier."""
        return None

    def get_user_groups(self, user_id: str) -> List[DirectoryGroup]:
        """Return all groups that contain *user_id* as a member."""
        return []
