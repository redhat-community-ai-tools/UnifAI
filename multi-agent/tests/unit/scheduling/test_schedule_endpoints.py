"""Unit tests for Flask API endpoints (schedules blueprint).

Covers: schedule.create, schedule.update, schedule.list, schedule.get,
        schedule.pause, schedule.resume, schedule.trigger,
        schedule.delete, schedule.runs.
(Test Plan sections 6.1–6.9)
"""
import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from mas.core.identity import Identity
from mas.scheduling.models import (
    ScheduleDefinition,
    ScheduleStatus,
    WorkflowSchedule,
)
from mas.scheduling.service import (
    ScheduleLimitExceededError,
    ScheduleNotFoundError,
    SchedulePermissionError,
)
from mas.blueprints.exceptions import BlueprintNotFoundError
from mas.session.domain.models import ScheduleRunSummary


@pytest.fixture
def identity():
    return Identity.user("test-user")


def _make_schedule(identity, **kwargs):
    text = kwargs.pop("text", "test prompt")
    inputs = kwargs.pop("inputs", None)
    if inputs is None:
        inputs = {"user_prompt": text}
    elif "user_prompt" not in inputs:
        inputs = {**inputs, "user_prompt": text}
    return WorkflowSchedule(
        blueprint_id=kwargs.get("blueprint_id", "bp-1"),
        identity=identity,
        inputs=inputs,
        schedule=ScheduleDefinition(interval=timedelta(minutes=15)),
        schedule_status=kwargs.get("status", ScheduleStatus.ACTIVE),
        engine_handle=kwargs.get("engine_handle", "sched-1"),
    )


@pytest.fixture
def mock_schedule_service():
    return Mock()


def _passthrough_decorator(f):
    """Bypass identity auth decorator for unit tests."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import g
        kwargs["identity"] = g.get("identity")
        return f(*args, **kwargs)

    return decorated


@pytest.fixture
def app(mock_schedule_service, identity):
    """Create Flask test app with mocked container and identity."""
    with patch(
        "inbound.flask.decorators.with_require_identity_authorization",
        _passthrough_decorator,
    ), patch(
        "inbound.flask.endpoints.schedules.with_require_identity_authorization",
        _passthrough_decorator,
    ):
        import importlib
        import inbound.flask.endpoints.schedules as schedules_mod
        schedules_mod.with_require_identity_authorization = _passthrough_decorator
        importlib.reload(schedules_mod)

        test_app = Flask(__name__)
        test_app.config["TESTING"] = True

        container = Mock()
        container.schedule_service = mock_schedule_service
        test_app.container = container

        test_app.register_blueprint(schedules_mod.schedules_bp, url_prefix="/api/schedules")

        @test_app.before_request
        def _inject_identity():
            from flask import g
            g.identity = identity

        yield test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ═══════════════════════════════════════════════════════════════════
# 6.1 POST /api/schedules/schedule.create
# ═══════════════════════════════════════════════════════════════════

class TestCreateEndpoint:
    def test_successful_creation(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity)
        mock_schedule_service.create.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.create",
            json={
                "blueprintId": "bp-1",
                "inputs": {"user_prompt": "Generate report"},
                "schedule": {"interval": "PT900S"},
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["blueprint_id"] == "bp-1"

    def test_blueprint_not_found(self, client, mock_schedule_service):
        mock_schedule_service.create.side_effect = BlueprintNotFoundError("bp-nope")
        resp = client.post(
            "/api/schedules/schedule.create",
            json={"blueprintId": "bp-nope", "inputs": {"user_prompt": "x"}, "schedule": {"interval": "PT60S"}},
        )
        assert resp.status_code == 404
        assert resp.get_json()["error_type"] == "BLUEPRINT_NOT_FOUND"

    def test_limit_exceeded(self, client, mock_schedule_service):
        mock_schedule_service.create.side_effect = ScheduleLimitExceededError("bp-1", 10)
        resp = client.post(
            "/api/schedules/schedule.create",
            json={"blueprintId": "bp-1", "inputs": {"user_prompt": "x"}, "schedule": {"interval": "PT60S"}},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error_type"] == "LIMIT_EXCEEDED"

    def test_invalid_schedule(self, client, mock_schedule_service):
        mock_schedule_service.create.side_effect = ValueError("bad schedule")
        resp = client.post(
            "/api/schedules/schedule.create",
            json={"blueprintId": "bp-1", "inputs": {"user_prompt": "x"}, "schedule": {}},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_type"] == "VALIDATION_ERROR"

    def test_source_shortcut_copy(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity)
        mock_schedule_service.create.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.create",
            json={
                "blueprintId": "bp-1",
                "inputs": {"user_prompt": "x"},
                "source": "shortcut_copy",
                "schedule": {"interval": "PT60S"},
            },
        )
        assert resp.status_code == 201
        assert mock_schedule_service.create.call_args[1]["source"] == "shortcut_copy"


# ═══════════════════════════════════════════════════════════════════
# 6.2 POST /api/schedules/schedule.update
# ═══════════════════════════════════════════════════════════════════

class TestUpdateEndpoint:
    def test_update_text(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity, text="updated")
        mock_schedule_service.update.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.update",
            json={"scheduleId": schedule.id, "inputs": {"user_prompt": "updated"}},
        )
        assert resp.status_code == 200
        assert resp.get_json()["inputs"]["user_prompt"] == "updated"

    def test_not_found(self, client, mock_schedule_service):
        mock_schedule_service.update.side_effect = ScheduleNotFoundError("bad-id")
        resp = client.post(
            "/api/schedules/schedule.update",
            json={"scheduleId": "bad-id", "inputs": {"user_prompt": "x"}},
        )
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_schedule_service, identity):
        mock_schedule_service.update.side_effect = SchedulePermissionError("x", identity)
        resp = client.post(
            "/api/schedules/schedule.update",
            json={"scheduleId": "x", "inputs": {"user_prompt": "y"}},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6.3 GET /api/schedules/schedule.list
# ═══════════════════════════════════════════════════════════════════

class TestListEndpoint:
    def test_list(self, client, mock_schedule_service, identity):
        mock_schedule_service.list_enriched.return_value = [
            _make_schedule(identity).model_dump(mode="json"),
        ]
        resp = client.get("/api/schedules/schedule.list")
        assert resp.status_code == 200
        assert len(resp.get_json()) == 1

    def test_list_with_blueprint_filter(self, client, mock_schedule_service):
        mock_schedule_service.list_enriched.return_value = []
        resp = client.get("/api/schedules/schedule.list?blueprintId=bp-1")
        assert resp.status_code == 200
        assert mock_schedule_service.list_enriched.call_args[1]["blueprint_id"] == "bp-1"


# ═══════════════════════════════════════════════════════════════════
# 6.4 GET /api/schedules/schedule.get
# ═══════════════════════════════════════════════════════════════════

class TestGetEndpoint:
    def test_get(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity)
        mock_schedule_service.get.return_value = schedule
        resp = client.get(f"/api/schedules/schedule.get?scheduleId={schedule.id}")
        assert resp.status_code == 200
        assert resp.get_json()["id"] == schedule.id

    def test_not_found(self, client, mock_schedule_service):
        mock_schedule_service.get.side_effect = ScheduleNotFoundError("bad-id")
        resp = client.get("/api/schedules/schedule.get?scheduleId=bad-id")
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 6.5 POST /api/schedules/schedule.pause
# ═══════════════════════════════════════════════════════════════════

class TestPauseEndpoint:
    def test_pause(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity, status=ScheduleStatus.PAUSED)
        mock_schedule_service.pause.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.pause",
            json={"scheduleId": schedule.id},
        )
        assert resp.status_code == 200
        assert resp.get_json()["schedule_status"] == "paused"


# ═══════════════════════════════════════════════════════════════════
# 6.6 POST /api/schedules/schedule.resume
# ═══════════════════════════════════════════════════════════════════

class TestResumeEndpoint:
    def test_resume(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity)
        mock_schedule_service.resume.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.resume",
            json={"scheduleId": schedule.id},
        )
        assert resp.status_code == 200
        assert resp.get_json()["schedule_status"] == "active"


# ═══════════════════════════════════════════════════════════════════
# 6.7 POST /api/schedules/schedule.trigger
# ═══════════════════════════════════════════════════════════════════

class TestTriggerEndpoint:
    def test_trigger(self, client, mock_schedule_service, identity):
        schedule = _make_schedule(identity)
        mock_schedule_service.trigger.return_value = schedule
        resp = client.post(
            "/api/schedules/schedule.trigger",
            json={"scheduleId": schedule.id},
        )
        assert resp.status_code == 200

    def test_trigger_no_temporal_schedule(self, client, mock_schedule_service):
        mock_schedule_service.trigger.side_effect = ValueError("No schedule")
        resp = client.post(
            "/api/schedules/schedule.trigger",
            json={"scheduleId": "x"},
        )
        assert resp.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 6.8 DELETE /api/schedules/schedule.delete
# ═══════════════════════════════════════════════════════════════════

class TestDeleteEndpoint:
    def test_delete(self, client, mock_schedule_service, identity):
        resp = client.delete(
            "/api/schedules/schedule.delete",
            json={"scheduleId": "sched-1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] is True

    def test_delete_not_found(self, client, mock_schedule_service):
        mock_schedule_service.delete.side_effect = ScheduleNotFoundError("bad-id")
        resp = client.delete(
            "/api/schedules/schedule.delete",
            json={"scheduleId": "bad-id"},
        )
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 6.9 GET /api/schedules/schedule.runs
# ═══════════════════════════════════════════════════════════════════

class TestRunsEndpoint:
    def test_get_runs(self, client, mock_schedule_service, identity):
        mock_schedule_service.get_runs.return_value = []
        resp = client.get("/api/schedules/schedule.runs?scheduleId=sched-1")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_runs_not_found(self, client, mock_schedule_service):
        mock_schedule_service.get_runs.side_effect = ScheduleNotFoundError("bad-id")
        resp = client.get("/api/schedules/schedule.runs?scheduleId=bad-id")
        assert resp.status_code == 404
