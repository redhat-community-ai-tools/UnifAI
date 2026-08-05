"""Unit tests for CollaborationService team edit lock methods.

Now that admin edit locks live in their own ``AdminEditLockService``,
the team-facing methods on ``CollaborationService`` no longer need a
sentinel guard against a magic admin namespace — the two authorization
models are structurally separated by belonging to different services.
"""
from unittest.mock import Mock

import pytest

from mas.collaboration.service import CollaborationService


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


class TestTeamEditLocks:
    def test_acquire_team_edit_lock_delegates_to_store(self, service):
        service._store.acquire_team_edit_lock.return_value = (True, None)
        acquired, holder = service.acquire_team_edit_lock(
            "team-eng-42", "resource", "some-rid", "alice",
        )
        assert acquired is True
        assert holder is None
        service._store.acquire_team_edit_lock.assert_called_once()

    def test_release_team_edit_lock_delegates_to_store(self, service):
        service.release_team_edit_lock("team-eng-42", "resource", "some-rid", "alice")
        service._store.release_team_edit_lock.assert_called_once()

    def test_renew_team_edit_lock_delegates_to_store(self, service):
        service._store.renew_team_edit_lock.return_value = True
        renewed = service.renew_team_edit_lock(
            "team-eng-42", "resource", "some-rid", "alice",
        )
        assert renewed is True

    def test_get_team_edit_lock_delegates_to_store(self, service):
        service._store.get_team_edit_lock.return_value = None
        holder = service.get_team_edit_lock(
            "team-eng-42", "resource", "some-rid", "alice",
        )
        assert holder is None

    def test_invalid_entity_kind_raises_value_error(self, service):
        with pytest.raises(ValueError, match="entityKind"):
            service.acquire_team_edit_lock(
                "team-eng-42", "invalid_kind", "some-rid", "alice",
            )
        service._store.acquire_team_edit_lock.assert_not_called()

    def test_non_member_rejected(self):
        class NeverMember:
            def is_member(self, username, team_id):
                return False

        svc = CollaborationService(
            store=Mock(), session_repo=Mock(), identity_provider=NeverMember(),
        )
        with pytest.raises(PermissionError):
            svc.acquire_team_edit_lock("team-1", "resource", "rid", "alice")
        svc._store.acquire_team_edit_lock.assert_not_called()
