"""
Domain models for multi-user session collaboration.

Collaboration state is *transient* (Redis-backed, not persisted to Mongo).
MongoDB remains the source of truth for session ownership; Redis tracks
who is currently active inside a session.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ParticipantRole(str, Enum):
    OWNER = "owner"
    COLLABORATOR = "collaborator"
    VIEWER = "viewer"


class Participant(BaseModel):
    """A user currently present in a session."""
    user_id: str
    display_name: str = ""
    role: ParticipantRole = ParticipantRole.COLLABORATOR
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionParticipants(BaseModel):
    """Snapshot of who is currently in a session."""
    session_id: str
    participants: List[Participant] = Field(default_factory=list)

    @property
    def user_ids(self) -> List[str]:
        return [p.user_id for p in self.participants]

    def has_user(self, user_id: str) -> bool:
        return any(p.user_id == user_id for p in self.participants)


class TeamSessionIndex(BaseModel):
    """Active sessions for a team (real-time view from Redis)."""
    team_id: str
    active_session_ids: List[str] = Field(default_factory=list)


class TeamEditLockHolder(BaseModel):
    """Who currently holds a team-scoped edit lock on a resource or blueprint."""
    user_id: str
    display_name: str = ""
