"""Admin edit lock service — cooperative locking for built-in resource mutations.

Wraps the same Redis-backed ``CollaborationStore`` as team edit locks but
uses a fixed admin namespace and kind.  Authorization is enforced at the
endpoint layer via ``@require_admin_access`` rather than team-membership
checks — structurally separating the two authorization models that were
previously tangled inside ``CollaborationService``.

Structurally satisfies the ``AdminEditLockReader`` protocol defined in
``mas.resources.ports``, so it can be injected directly into
``ResourcesService.guard_write_access`` without an adapter wrapper.
"""
from typing import Optional, Tuple

from mas.collaboration.models import TeamEditLockHolder
from mas.collaboration.ports import CollaborationStore

ADMIN_LOCK_NAMESPACE = "__admin__"
BUILTIN_LOCK_KIND = "builtin"


class AdminEditLockService:
    """Cooperative edit locks for admin mutations on built-in resources.

    Each method delegates to the same Redis lock primitive that team edit
    locks use (``CollaborationStore.acquire_team_edit_lock`` etc.), but
    with a fixed ``(namespace, kind)`` pair so all admin locks share one
    global namespace and skip team-membership checks entirely.
    """

    def __init__(self, store: CollaborationStore, edit_lock_ttl: int = 180):
        self._store = store
        self._edit_lock_ttl = edit_lock_ttl

    def acquire(
        self, entity_id: str, user_id: str,
    ) -> Tuple[bool, Optional[TeamEditLockHolder]]:
        return self._store.acquire_team_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id,
            user_id, user_id, ttl=self._edit_lock_ttl,
        )

    def release(self, entity_id: str, user_id: str) -> None:
        self._store.release_team_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id, user_id,
        )

    def renew(self, entity_id: str, user_id: str) -> bool:
        return self._store.renew_team_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id,
            user_id, user_id, ttl=self._edit_lock_ttl,
        )

    def get_admin_edit_lock(
        self, entity_id: str,
    ) -> Optional[TeamEditLockHolder]:
        """Return the current lock holder, or ``None`` if unlocked.

        Named to match the ``AdminEditLockReader`` protocol so this
        service satisfies it structurally.
        """
        return self._store.get_team_edit_lock(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, entity_id,
        )
