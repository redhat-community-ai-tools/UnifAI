"""
Port (abstract interface) for the collaboration store.

Implementations provide the backing storage for real-time participant
tracking and team-session indexing.  The default implementation uses
Redis; a local in-memory fallback is possible for tests or single-node
deployments.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .models import Participant, SessionParticipants, TeamEditLockHolder, TeamSessionIndex


class CollaborationStore(ABC):
    """Transient, real-time collaboration state (not persisted to Mongo)."""

    # ── Participant presence ────────────────────────────────────────

    @abstractmethod
    def add_participant(
        self,
        session_id: str,
        participant: Participant,
        ttl: int = 300,
    ) -> None:
        """Register a participant in a session. TTL (seconds) controls auto-expiry."""
        ...

    @abstractmethod
    def remove_participant(self, session_id: str, user_id: str) -> None:
        """Remove a participant from a session."""
        ...

    @abstractmethod
    def heartbeat(self, session_id: str, user_id: str, ttl: int = 300) -> None:
        """Refresh the presence TTL for a participant."""
        ...

    @abstractmethod
    def get_participants(self, session_id: str) -> SessionParticipants:
        """Get all currently active participants in a session."""
        ...

    # ── Team-session index ──────────────────────────────────────────

    @abstractmethod
    def register_team_session(self, team_id: str, session_id: str) -> None:
        """Add a session to the team's active-session set."""
        ...

    @abstractmethod
    def unregister_team_session(self, team_id: str, session_id: str) -> None:
        """Remove a session from the team's active-session set."""
        ...

    @abstractmethod
    def get_team_sessions(self, team_id: str) -> TeamSessionIndex:
        """List all active sessions for a team."""
        ...

    # ── User-to-sessions mapping ────────────────────────────────────

    @abstractmethod
    def get_user_sessions(self, user_id: str) -> List[str]:
        """List session IDs a user is currently participating in."""
        ...

    # ── Typing indicators ────────────────────────────────────────────

    @abstractmethod
    def set_typing(self, session_id: str, user_id: str, ttl: int = 5) -> None:
        """Mark a user as currently typing (auto-expires after *ttl* seconds)."""
        ...

    @abstractmethod
    def clear_typing(self, session_id: str, user_id: str) -> None:
        """Explicitly clear the typing indicator for a user."""
        ...

    @abstractmethod
    def get_typing_users(self, session_id: str) -> list[str]:
        """Return user IDs that currently have an active typing indicator."""
        ...

    # ── Health ──────────────────────────────────────────────────────

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the backing store is reachable."""
        ...

    # ── Team edit locks (resources / blueprints) ─────────────────────

    @abstractmethod
    def acquire_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
        display_name: str,
        ttl: int,
    ) -> tuple[bool, Optional[TeamEditLockHolder]]:
        """
        Attempt to take (or renew) an edit lock.

        Returns ``(True, None)`` on success. If another user holds the lock,
        returns ``(False, holder)``.
        """
        ...

    @abstractmethod
    def release_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> None:
        """Remove the lock only if *user_id* is the current holder."""
        ...

    @abstractmethod
    def renew_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
        display_name: str,
        ttl: int,
    ) -> bool:
        """Refresh TTL if *user_id* holds the lock. Returns whether renew succeeded."""
        ...

    @abstractmethod
    def get_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
    ) -> Optional[TeamEditLockHolder]:
        """Return current lock holder, if any."""
        ...

    @abstractmethod
    def get_team_edit_locks_batch(
        self,
        team_id: str,
        entity_kind: str,
        entity_ids: list[str],
    ) -> Dict[str, Optional[TeamEditLockHolder]]:
        """Return lock holder per entity id (``None`` if unlocked)."""
        ...
