from datetime import datetime
from enum import Enum
from typing import List
from uuid import uuid4

from pydantic import BaseModel, Field


class TeamMemberType(str, Enum):
    USER = "user"
    GROUP = "group"


class TeamMember(BaseModel):
    """A member entry in a team — either an individual user or an LDAP group."""
    type: TeamMemberType
    id: str
    display_name: str = ""
    group_members: List[str] = Field(default_factory=list)


class Team(BaseModel):
    team_id: str = Field(default_factory=lambda: uuid4().hex)
    name: str
    created_by: str
    members: List[TeamMember] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    def effective_member_count(self) -> int:
        """Unique individual users: direct users + users inside groups."""
        ids: set = set()
        for m in self.members:
            if m.type == TeamMemberType.USER:
                ids.add(m.id)
            elif m.type == TeamMemberType.GROUP and m.group_members:
                ids.update(m.group_members)
        return len(ids)
