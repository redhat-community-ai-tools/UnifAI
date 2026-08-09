"""Unit tests for AdminEditLockService.

Admin edit locks are structurally separated from team edit locks:
they share the same Redis lock primitive (``CollaborationStore``)
but use a fixed namespace/kind and skip team-membership checks —
authorization is enforced by ``@require_admin_access`` at the endpoint
layer instead.
"""
from unittest.mock import Mock

import pytest

from mas.collaboration.models import TeamEditLockHolder
from mas.resources.admin_edit_lock_service import (
    ADMIN_LOCK_NAMESPACE,
    BUILTIN_LOCK_KIND,
    AdminEditLockService,
)


@pytest.fixture
def store():
    return Mock()


@pytest.fixture
def service(store) -> AdminEditLockService:
    return AdminEditLockService(store=store, edit_lock_ttl=180)


class TestAcquire:
    def test_acquire_delegates_to_store_with_admin_namespace(self, service, store):
        store.acquire_team_edit_lock.return_value = (True, None)

        acquired, holder = service.acquire("some-rid", "admin-1")

        assert acquired is True
        assert holder is None
        store.acquire_team_edit_lock.assert_called_once_with(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid",
            "admin-1", "admin-1", ttl=180,
        )

    def test_acquire_returns_holder_when_locked_by_another(self, service, store):
        other = TeamEditLockHolder(user_id="other-admin", display_name="Other")
        store.acquire_team_edit_lock.return_value = (False, other)

        acquired, holder = service.acquire("some-rid", "admin-1")

        assert acquired is False
        assert holder.user_id == "other-admin"


class TestRelease:
    def test_release_delegates_to_store(self, service, store):
        service.release("some-rid", "admin-1")

        store.release_team_edit_lock.assert_called_once_with(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid", "admin-1",
        )


class TestRenew:
    def test_renew_delegates_to_store(self, service, store):
        store.renew_team_edit_lock.return_value = True

        renewed = service.renew("some-rid", "admin-1")

        assert renewed is True
        store.renew_team_edit_lock.assert_called_once_with(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid",
            "admin-1", "admin-1", ttl=180,
        )


class TestGetAdminEditLock:
    def test_returns_none_when_unlocked(self, service, store):
        store.get_team_edit_lock.return_value = None

        holder = service.get_admin_edit_lock("some-rid")

        assert holder is None
        store.get_team_edit_lock.assert_called_once_with(
            ADMIN_LOCK_NAMESPACE, BUILTIN_LOCK_KIND, "some-rid",
        )

    def test_returns_holder_when_locked(self, service, store):
        expected = TeamEditLockHolder(user_id="admin-1", display_name="Admin")
        store.get_team_edit_lock.return_value = expected

        holder = service.get_admin_edit_lock("some-rid")

        assert holder.user_id == "admin-1"


class TestAdminEditLockReaderProtocol:
    """AdminEditLockService structurally satisfies the AdminEditLockReader
    protocol — verify it passes a runtime_checkable isinstance test."""

    def test_satisfies_protocol(self, service):
        from mas.resources.ports import AdminEditLockReader
        assert isinstance(service, AdminEditLockReader)
