"""Abstract team repository interface."""
from abc import ABC, abstractmethod
from typing import List, Optional

from teams.models import Team


class TeamRepository(ABC):

    @abstractmethod
    def create(self, doc: Team) -> str:
        """Persist a new team. Returns the team_id."""

    @abstractmethod
    def get(self, team_id: str) -> Team:
        """Retrieve a team by ID. Raises KeyError if not found."""

    @abstractmethod
    def find_by_member(self, member_id: str,
                       group_ids: Optional[List[str]] = None) -> List[Team]:
        """Return all teams that include *member_id* or any of *group_ids*."""

    @abstractmethod
    def find_by_name(self, name: str) -> Optional[Team]:
        """Return the team with the given name, or None."""

    @abstractmethod
    def update(self, doc: Team) -> str:
        """Replace an existing team. Raises KeyError if not found."""

    @abstractmethod
    def delete(self, team_id: str) -> None:
        """Delete a team by ID. Raises KeyError if not found."""

    def update_group_members(self, group_id: str,
                             member_ids: List[str]) -> int:
        """Refresh the stored *group_members* list for every team that
        contains a group entry with the given *group_id*.
        Returns the number of modified documents."""
        return 0
