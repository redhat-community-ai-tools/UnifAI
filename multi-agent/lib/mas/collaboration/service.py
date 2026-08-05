"""
Collaboration service — domain logic for multi-user session participation.

Orchestrates participant tracking, team-session indexing, and ensures
that Temporal-backed sessions can be shared across team members through
the existing Redis Streams channel infrastructure.
"""
import logging
from typing import Dict, List, Optional, Tuple

from mas.core.identity import IdentityType
from mas.core.identity.ports import IdentityProvider
from mas.session.domain.session_record import SessionRecord
from mas.session.repository.repository import SessionRepository
from .models import (
    Participant,
    ParticipantRole,
    SessionParticipants,
    TeamEditLockHolder,
    TeamSessionIndex,
)
from .ports import CollaborationStore

logger = logging.getLogger(__name__)

BUILTIN_LOCK_KIND = "builtin"

EDIT_LOCK_KINDS: frozenset[str] = frozenset({"resource", "blueprint", BUILTIN_LOCK_KIND})

ADMIN_LOCK_NAMESPACE = "__admin__"


class CollaborationService:
    """
    Application-level facade for session collaboration.

    Coordinates between:
    - ``CollaborationStore`` (Redis) for transient participant presence
    - ``SessionRepository`` (Mongo) for persistent ownership checks
    - ``IdentityProvider`` for team-membership authorization
    - Existing Redis Streams channel for real-time event delivery
    """

    def __init__(
        self,
        store: CollaborationStore,
        session_repo: SessionRepository,
        identity_provider: IdentityProvider,
        presence_ttl: int = 300,
        edit_lock_ttl: int = 180,
        typing_ttl: int = 5,
    ):
        self._store = store
        self._session_repo = session_repo
        self._identity_provider = identity_provider
        self._presence_ttl = presence_ttl
        self._edit_lock_ttl = edit_lock_ttl
        self._typing_ttl = typing_ttl

    # ── Authorization ──────────────────────────────────────────────

    def check_session_access(self, user_id: str, session_id: str) -> SessionRecord:
        """Verify the user owns (or is a team member of) the session.

        Returns the session record on success.
        Raises ``KeyError`` if the session does not exist.
        Raises ``PermissionError`` if the user does not have access.
        """
        record = self._session_repo.fetch(session_id)
        if record.identity.type == IdentityType.TEAM:
            if not self._identity_provider.is_member(user_id, record.identity.id):
                raise PermissionError("Access denied")
        elif user_id.casefold() != record.identity.id.casefold():
            raise PermissionError("Access denied")
        return record

    def check_team_membership(self, user_id: str, team_id: str) -> None:
        """Verify the user is a member of the team.

        Raises ``PermissionError`` if the user is not a member, or if
        ``team_id`` is the reserved ``ADMIN_LOCK_NAMESPACE`` sentinel —
        team-facing callers (edit locks, team sessions) must never be able
        to operate in the admin lock namespace just because an identity
        provider happens to consider the caller a "member" of it (e.g.
        ``DevIdentityProvider.is_member()`` always returns ``True``). Real
        admin access to that namespace goes exclusively through
        ``acquire_admin_edit_lock``/``release_admin_edit_lock``/etc., which
        skip this check entirely and rely on ``@require_admin_access`` at
        the endpoint layer instead.
        """
        if team_id == ADMIN_LOCK_NAMESPACE:
            raise PermissionError("Access denied: reserved namespace")
        if not self._identity_provider.is_member(user_id, team_id):
            raise PermissionError("Access denied: you are not a member of this team")

    @staticmethod
    def validate_edit_lock_kind(entity_kind: str) -> None:
        """Validate that entity_kind is a supported lock type.

        Raises ``ValueError`` if the kind is not recognised.
        """
        if entity_kind not in EDIT_LOCK_KINDS:
            raise ValueError(
                f"entityKind must be one of: {', '.join(sorted(EDIT_LOCK_KINDS))}"
            )

    # ── Join / Leave ────────────────────────────────────────────────

    def join_session(
        self,
        session_id: str,
        user_id: str,
        role: str = "collaborator",
    ) -> SessionParticipants:
        """
        Add a user to a session's participant list.

        ``role`` is a raw string ("owner", "collaborator", "viewer") —
        conversion and validation happen here in the service layer.

        If the session is team-owned, the session is also registered
        in the team's active-session index.

        Returns the updated participant list.
        """
        participant_role = ParticipantRole(role)
        record = self._session_repo.fetch(session_id)

        if record.identity.id == user_id:
            participant_role = ParticipantRole.OWNER

        participant = Participant(
            user_id=user_id,
            display_name=user_id,
            role=participant_role,
        )
        self._store.add_participant(session_id, participant, ttl=self._presence_ttl)

        if record.identity.type == IdentityType.TEAM:
            self._store.register_team_session(record.identity.id, session_id)

        participants = self._store.get_participants(session_id)
        self._reconcile_team_session_index_if_empty(session_id, record, participants)
        return participants

    def leave_session(self, session_id: str, user_id: str) -> None:
        """Remove a user from a session's participant list."""
        self._store.remove_participant(session_id, user_id)

        participants = self._store.get_participants(session_id)
        try:
            record = self._session_repo.fetch(session_id)
        except KeyError:
            record = None
        if record is not None:
            self._reconcile_team_session_index_if_empty(session_id, record, participants)

    def heartbeat(self, session_id: str, user_id: str) -> None:
        """Refresh presence TTL for a user in a session."""
        self._store.heartbeat(session_id, user_id, ttl=self._presence_ttl)

    # ── Queries ─────────────────────────────────────────────────────

    def get_participants(self, session_id: str, user_id: str) -> SessionParticipants:
        """Return live participants; drop stale team-session index when everyone TTL'd out.

        Validates that ``user_id`` has access to the session before returning.
        """
        self.check_session_access(user_id, session_id)
        participants = self._store.get_participants(session_id)
        try:
            record = self._session_repo.fetch(session_id)
        except KeyError:
            return participants
        self._reconcile_team_session_index_if_empty(session_id, record, participants)
        return participants

    def _reconcile_team_session_index_if_empty(
        self,
        session_id: str,
        record: SessionRecord,
        participants: SessionParticipants,
    ) -> None:
        if record.identity.type != IdentityType.TEAM:
            return
        if participants.participants:
            return
        self._store.unregister_team_session(record.identity.id, session_id)

    def get_team_sessions(self, team_id: str, user_id: str) -> TeamSessionIndex:
        self.check_team_membership(user_id, team_id)
        return self._store.get_team_sessions(team_id)

    def get_user_active_sessions(self, user_id: str) -> List[str]:
        """Sessions the user is currently participating in (across all teams)."""
        return self._store.get_user_sessions(user_id)

    # ── Typing ──────────────────────────────────────────────────────

    def set_typing(self, session_id: str, user_id: str) -> None:
        self._store.set_typing(session_id, user_id, ttl=self._typing_ttl)

    def clear_typing(self, session_id: str, user_id: str) -> None:
        self._store.clear_typing(session_id, user_id)

    def get_typing_users(self, session_id: str, user_id: str | None = None) -> list[str]:
        """Return user IDs currently typing.

        When *user_id* is provided, session access is validated first.
        The parameter is optional for backward-compat with internal
        callers (e.g. session-meta enrichment) that already verified access.
        """
        if user_id is not None:
            self.check_session_access(user_id, session_id)
        return self._store.get_typing_users(session_id)

    def is_available(self) -> bool:
        return self._store.is_available()

    # ── Edit locks (shared primitive) ────────────────────────────────
    #
    # Team and admin edit locks are the *same* underlying Redis lock,
    # keyed by (namespace, kind, entity_id). "Team" locks scope the
    # namespace to a real team_id and require team membership; "admin"
    # locks scope it to a fixed sentinel namespace (``ADMIN_LOCK_NAMESPACE``)
    # and skip that check because authorization is already enforced at the
    # endpoint layer via ``@require_admin_access``. These private helpers
    # hold the one implementation; the public methods below only differ in
    # which authorization check (if any) they run and which namespace/kind
    # they pass through.

    def _acquire_edit_lock(
        self, namespace: str, kind: str, entity_id: str, user_id: str,
    ) -> Tuple[bool, Optional[TeamEditLockHolder]]:
        return self._store.acquire_team_edit_lock(
            namespace, kind, entity_id, user_id, user_id, ttl=self._edit_lock_ttl,
        )

    def _release_edit_lock(
        self, namespace: str, kind: str, entity_id: str, user_id: str,
    ) -> None:
        self._store.release_team_edit_lock(namespace, kind, entity_id, user_id)

    def _renew_edit_lock(
        self, namespace: str, kind: str, entity_id: str, user_id: str,
    ) -> bool:
        return self._store.renew_team_edit_lock(
            namespace, kind, entity_id, user_id, user_id, ttl=self._edit_lock_ttl,
        )

    def _get_edit_lock(
        self, namespace: str, kind: str, entity_id: str,
    ) -> Optional[TeamEditLockHolder]:
        return self._store.get_team_edit_lock(namespace, kind, entity_id)

    def _get_edit_locks_batch(
        self, namespace: str, kind: str, entity_ids: list[str],
    ) -> Dict[str, Optional[TeamEditLockHolder]]:
        return self._store.get_team_edit_locks_batch(namespace, kind, entity_ids)

    # ── Team edit locks ─────────────────────────────────────────────

    def acquire_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> Tuple[bool, Optional[TeamEditLockHolder]]:
        self.check_team_membership(user_id, team_id)
        self.validate_edit_lock_kind(entity_kind)
        return self._acquire_edit_lock(team_id, entity_kind, entity_id, user_id)

    def release_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> None:
        self.check_team_membership(user_id, team_id)
        self.validate_edit_lock_kind(entity_kind)
        self._release_edit_lock(team_id, entity_kind, entity_id, user_id)

    def renew_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> bool:
        self.check_team_membership(user_id, team_id)
        self.validate_edit_lock_kind(entity_kind)
        return self._renew_edit_lock(team_id, entity_kind, entity_id, user_id)

    def get_team_edit_lock(
        self,
        team_id: str,
        entity_kind: str,
        entity_id: str,
        user_id: str,
    ) -> Optional[TeamEditLockHolder]:
        self.check_team_membership(user_id, team_id)
        self.validate_edit_lock_kind(entity_kind)
        return self._get_edit_lock(team_id, entity_kind, entity_id)

    def get_team_edit_locks_batch(
        self,
        team_id: str,
        entity_kind: str,
        entity_ids: list[str],
        user_id: str,
    ) -> Dict[str, Optional[TeamEditLockHolder]]:
        self.check_team_membership(user_id, team_id)
        self.validate_edit_lock_kind(entity_kind)
        return self._get_edit_locks_batch(team_id, entity_kind, entity_ids)

    # ── Admin edit locks (built-in resources) ─────────────────────────
    #
    # Same lock primitive as team locks (see helpers above), fixed to a
    # sentinel namespace/kind so all admin locks are globally visible and
    # skip team-membership checks (admin-only access is enforced by the
    # @require_admin_access endpoint decorator instead).

    def acquire_admin_edit_lock(
        self,
        entity_id: str,
        user_id: str,
    ) -> Tuple[bool, Optional[TeamEditLockHolder]]:
        return self._acquire_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id, user_id,
        )

    def release_admin_edit_lock(
        self,
        entity_id: str,
        user_id: str,
    ) -> None:
        self._release_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id, user_id,
        )

    def renew_admin_edit_lock(
        self,
        entity_id: str,
        user_id: str,
    ) -> bool:
        return self._renew_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id, user_id,
        )

    def get_admin_edit_lock(
        self,
        entity_id: str,
    ) -> Optional[TeamEditLockHolder]:
        return self._get_edit_lock(ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id)

