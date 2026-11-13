"""Session expiry must fail closed at the shared authentication boundary."""
from datetime import datetime
from unittest.mock import Mock

import pytest

from global_utils.flask.decorators import validate_session
from global_utils.redis.constants import identity_session_key


@pytest.mark.parametrize("expiry", [None, 0, -1])
def test_missing_or_expired_session_is_rejected(expiry):
    payload = {"username": "alice", "access_token": "test-token"}
    if expiry is not None:
        payload["session_expires_at"] = expiry
    store = Mock()
    store.hget.return_value = payload

    user, error = validate_session(lambda: store, lambda: "session-id")

    assert user is None
    assert error == ("Session expired", "SESSION_EXPIRED", 401)
    store.hget.assert_called_once_with(identity_session_key("session-id"))


def test_valid_session_is_accepted():
    store = Mock()
    store.hget.return_value = {
        "username": "alice", "access_token": "test-token",
        "session_expires_at": datetime.now().timestamp() + 3600,
    }

    user, error = validate_session(lambda: store, lambda: "session-id")

    assert error is None
    assert user.username == "alice"
