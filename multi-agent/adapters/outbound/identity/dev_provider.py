"""
Local development adapter — always permits access, no real team checks.

Use when running MAS without the Identity pod (e.g. local docker-compose
without the shared-resources/identity service).
"""
from typing import Optional

from mas.core.identity.ports import IdentityProvider


class DevIdentityProvider(IdentityProvider):
    """Dev mode: no authentication required, all team membership checks pass."""

    @property
    def requires_authentication(self) -> bool:
        return False

    def is_member(self, username: str, team_id: str) -> bool:
        return True

    def get_team_ids(self, username: str) -> frozenset[str]:
        return frozenset()

    def resolve_team_id(self, username: str, raw: str) -> Optional[str]:
        return raw

    def resolve_team_display_name(self, username: str, team_id: str) -> str:
        return team_id
