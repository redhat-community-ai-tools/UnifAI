"""A failure while building a session's elements marks it FAILED and raises a safe error."""
import logging
from unittest.mock import MagicMock

import pytest

from mas.elements.common.exceptions import PluginConfigurationError
from mas.session.domain.exceptions import BlueprintNotFoundError, SessionBuildError
from mas.session.domain.models import SessionMeta
from mas.session.domain.status import SessionStatus
from mas.session.service import SessionService


def _service(build_error: Exception):
    record = MagicMock()
    record.metadata = SessionMeta()
    record.status = SessionStatus.PENDING
    manager = MagicMock()
    manager.get_session.side_effect = build_error
    manager.get_record.return_value = record
    foreground = MagicMock()
    svc = SessionService(manager, foreground, MagicMock())
    return svc, manager, record, foreground


def test_build_error_marks_session_failed_and_stores_safe_error(caplog):
    secret = "sk-very-secret"
    err = PluginConfigurationError("Invalid qdrant settings", {"api_key": secret})
    svc, manager, record, foreground = _service(err)

    with caplog.at_level(logging.ERROR), pytest.raises(SessionBuildError) as exc:
        svc.run("s-1", {}, stream=True)

    assert record.status == SessionStatus.FAILED
    manager.save_record.assert_called_with(record)
    stored = record.metadata.error
    assert stored["type"] == "session_build_failed"
    assert "Invalid qdrant settings" in stored["message"]
    assert secret not in stored["message"] and secret not in str(exc.value)
    assert exc.value.__cause__ is err
    assert any(r.exc_info for r in caplog.records)  # full exception logged server-side
    foreground.run.assert_not_called()


def test_unexpected_error_message_does_not_leak_exception_text():
    svc, _, record, _ = _service(RuntimeError("password=hunter2 at /srv/app.py"))

    with pytest.raises(SessionBuildError) as exc:
        svc.run("s-1", {})

    assert exc.value.message == "Session build failed (RuntimeError)"
    assert "hunter2" not in record.metadata.status_message


def test_missing_blueprint_is_not_a_build_failure():
    svc, _, record, _ = _service(BlueprintNotFoundError("bp", session_id="s-1"))

    with pytest.raises(BlueprintNotFoundError):
        svc.run("s-1", {})
    assert record.status == SessionStatus.PENDING
