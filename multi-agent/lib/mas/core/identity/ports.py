"""
Port for identity authorization and team membership operations.

The domain defines WHAT it needs from the outside world.
Adapters decide HOW to provide it.
"""
from abc import ABC, abstractmethod
from typing import Optional


class IdentityProvider(ABC):
    """Abstract interface for identity authorization and team membership.

    Each adapter implements a different policy (production HTTP checks,
    permissive dev mode, or no-op single-user mode).
    """

    @property
    @abstractmethod
    def requires_authentication(self) -> bool:
        """Whether HTTP requests must carry X-Authenticated-User.

        True  → requests without the header get 401.
        False → anonymous/unauthenticated access is permitted.
        """
        ...

    @abstractmethod
    def is_member(self, username: str, team_id: str) -> bool:
        """Check if the user is a member of the given team."""
        ...

    @abstractmethod
    def get_team_ids(self, username: str) -> frozenset[str]:
        """Return all team IDs the user belongs to."""
        ...

    @abstractmethod
    def resolve_team_id(self, username: str, raw: str) -> Optional[str]:
        """Map a team display-name or raw ID to the canonical team_id.

        Returns None if no matching team is found.
        """
        ...

    @abstractmethod
    def resolve_team_display_name(self, username: str, team_id: str) -> str:
        """Return the human-readable display name for a team."""
        ...
