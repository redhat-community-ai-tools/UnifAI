"""
No-op adapter — single-user mode with no team features.

Use when team functionality is not needed at all (e.g. personal/demo instances).
"""
from typing import Optional

from mas.core.identity.ports import IdentityProvider


class NoOpIdentityProvider(IdentityProvider):
    """Single-user mode: no authentication, no teams."""

    @property
    def requires_authentication(self) -> bool:
        return False

    def is_member(self, username: str, team_id: str) -> bool:
        return False

    def get_team_ids(self, username: str) -> frozenset[str]:
        return frozenset()

    def resolve_team_id(self, username: str, raw: str) -> Optional[str]:
        return None

    def resolve_team_display_name(self, username: str, team_id: str) -> str:
        return team_id
