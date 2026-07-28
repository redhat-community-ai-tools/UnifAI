"""Regression tests: team-facing edit-lock methods must never be able to
operate in the reserved admin lock namespace, even if the configured
``IdentityProvider`` would otherwise consider the caller a team "member"
(e.g. ``DevIdentityProvider.is_member()`` always returns ``True``). Real
admin access to that namespace goes exclusively through the dedicated
``*_admin_edit_lock`` methods, which bypass team-membership checks entirely
and rely on ``@require_admin_access`` at the endpoint layer instead.
"""
from unittest.mock import Mock

import pytest

from mas.collaboration.service import (
    ADMIN_LOCK_NAMESPACE,
    BUILTIN_LOCK_KIND,
    CollaborationService,
)


class AlwaysMemberIdentityProvider:
    """Mimics ``DevIdentityProvider``: every membership check passes."""

    def is_member(self, username: str, team_id: str) -> bool:
        return True


@pytest.fixture
def service() -> CollaborationService:
    return CollaborationService(
        store=Mock(),
        session_repo=Mock(),
        identity_provider=AlwaysMemberIdentityProvider(),
    )


class TestAdminNamespaceIsolation:
    def test_check_team_membership_rejects_admin_namespace(self, service):
        with pytest.raises(PermissionError):
            service.check_team_membership("alice", ADMIN_LOCK_NAMESPACE)

    def test_acquire_team_edit_lock_rejects_admin_namespace(self, service):
        """Even though the identity provider says 'alice' is a member of
        every team, a request scoped to the admin namespace must still be
        rejected before it ever reaches the shared lock primitive."""
        with pytest.raises(PermissionError):
            service.acquire_team_edit_lock(
                ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "alice",
            )
        service._store.acquire_team_edit_lock.assert_not_called()

    def test_release_team_edit_lock_rejects_admin_namespace(self, service):
        with pytest.raises(PermissionError):
            service.release_team_edit_lock(
                ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "alice",
            )
        service._store.release_team_edit_lock.assert_not_called()

    def test_renew_team_edit_lock_rejects_admin_namespace(self, service):
        with pytest.raises(PermissionError):
            service.renew_team_edit_lock(
                ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "alice",
            )
        service._store.renew_team_edit_lock.assert_not_called()

    def test_get_team_edit_lock_rejects_admin_namespace(self, service):
        with pytest.raises(PermissionError):
            service.get_team_edit_lock(
                ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "alice",
            )
        service._store.get_team_edit_lock.assert_not_called()

    def test_normal_team_namespace_still_works(self, service):
        """Sanity check: the guard only targets the reserved sentinel, not
        legitimate team ids."""
        service._store.acquire_team_edit_lock.return_value = (True, None)
        acquired, holder = service.acquire_team_edit_lock(
            "team-eng-42", "resource", "some-rid", "alice",
        )
        assert acquired is True
        assert holder is None

    def test_admin_edit_lock_bypasses_team_membership_check(self, service):
        """`acquire_admin_edit_lock` must keep working — it never calls
        `check_team_membership`, so it isn't affected by this guard."""
        service._store.acquire_team_edit_lock.return_value = (True, None)
        acquired, holder = service.acquire_admin_edit_lock("some-rid", "admin-1")
        assert acquired is True
        service._store.acquire_team_edit_lock.assert_called_once_with(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "admin-1", "admin-1", ttl=180,
        )
