"""Unit tests for SessionService.get_session_detail ownership enforcement.

Validates that the service layer:
- Returns SessionDetail when identity matches the session owner
- Raises PermissionError for non-owners (before accessing any other data)
- Propagates KeyError from the repository when the session is missing
"""
from unittest.mock import Mock

import pytest

from mas.core.identity import Identity
from mas.session.domain.models import SessionChat, SessionMeta
from mas.session.service import SessionService


@pytest.fixture
def owner():
    return Identity.user("owner-1")


@pytest.fixture
def other_user():
    return Identity.user("other-user")


@pytest.fixture
def mock_manager():
    return Mock()


@pytest.fixture
def service(mock_manager):
    svc = object.__new__(SessionService)
    svc._manager = mock_manager
    return svc


def _make_record(owner, *, status_name="COMPLETED"):
    record = Mock()
    record.identity = owner
    record.blueprint_id = "bp-1"
    record.status.name = status_name
    record.metadata = SessionMeta()
    record.run_context.started_at = None
    record.run_context.finished_at = None
    return record


class TestGetSessionDetailOwnership:
    def test_owner_receives_detail(self, service, mock_manager, owner):
        record = _make_record(owner)
        mock_manager.get_record.return_value = record
        mock_manager.get_blueprint_name.return_value = "My Blueprint"
        mock_manager.get_chat.return_value = SessionChat()

        detail = service.get_session_detail(session_id="sess-1", identity=owner)

        assert detail.session_id == "sess-1"
        assert detail.blueprint_id == "bp-1"
        mock_manager.get_record.assert_called_once_with("sess-1")

    def test_non_owner_raises_permission_error(
        self, service, mock_manager, owner, other_user,
    ):
        record = _make_record(owner)
        mock_manager.get_record.return_value = record

        with pytest.raises(PermissionError, match="not owned"):
            service.get_session_detail(session_id="sess-1", identity=other_user)

        mock_manager.get_chat.assert_not_called()
        mock_manager.get_blueprint_name.assert_not_called()

    def test_missing_session_raises_key_error(
        self, service, mock_manager, owner,
    ):
        mock_manager.get_record.side_effect = KeyError("No session for sess-nope")

        with pytest.raises(KeyError, match="No session"):
            service.get_session_detail(session_id="sess-nope", identity=owner)
