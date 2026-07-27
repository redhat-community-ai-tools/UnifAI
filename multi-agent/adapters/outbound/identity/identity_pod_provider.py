"""
Production adapter — delegates to the Identity pod via HTTP.

This is the ONLY place in the MAS codebase that imports global_utils.identity_client
for team-membership operations. The domain never touches it directly.
"""
import logging
from typing import Optional

from mas.core.identity.ports import IdentityProvider
from global_utils.identity_client import IdentityClient

logger = logging.getLogger(__name__)


class IdentityPodProvider(IdentityProvider):
    """Production adapter: all team checks go through the Identity pod HTTP API."""

    def __init__(self, identity_client: IdentityClient):
        self._client = identity_client

    @property
    def requires_authentication(self) -> bool:
        return True

    def is_member(self, username: str, team_id: str) -> bool:
        return self._client.is_member(username, team_id)

    def get_team_ids(self, username: str) -> frozenset[str]:
        return self._client.get_team_ids(username)

    def resolve_team_id(self, username: str, raw: str) -> Optional[str]:
        return self._client.resolve_team_id(username, raw)

    def resolve_team_display_name(self, username: str, team_id: str) -> str:
        return self._client.resolve_team_display_name(username, team_id)
