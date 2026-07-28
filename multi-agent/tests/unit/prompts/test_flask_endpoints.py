"""Unit tests for Flask API endpoints (prompts blueprint).

Covers: prompt.create, prompt.update, prompt.list, prompt.get,
        prompt.schedule.pause, prompt.schedule.resume, prompt.schedule.trigger,
        prompt.delete, prompt.runs.
(Test Plan sections 6.1–6.9)
"""
import json
from datetime import timedelta
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from mas.core.identity import Identity
from mas.prompts.models import (
    ScheduleDefinition,
    ScheduleStatus,
    ScheduledPrompt,
)
from mas.prompts.service import (
    PromptLimitExceededError,
    PromptNotFoundError,
    PromptPermissionError,
)
from mas.blueprints.exceptions import BlueprintNotFoundError
from mas.session.domain.models import ScheduleRunSummary


@pytest.fixture
def identity():
    return Identity.user("test-user")


def _make_prompt(identity, **kwargs):
    return ScheduledPrompt(
        blueprint_id=kwargs.get("blueprint_id", "bp-1"),
        identity=identity,
        text=kwargs.get("text", "test prompt"),
        schedule=ScheduleDefinition(interval=timedelta(minutes=15)),
        schedule_status=kwargs.get("status", ScheduleStatus.ACTIVE),
        temporal_schedule_id=kwargs.get("temporal_schedule_id", "sched-1"),
    )


@pytest.fixture
def mock_prompt_service():
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
def app(mock_prompt_service, identity):
    """Create Flask test app with mocked container and identity."""
    with patch(
        "inbound.flask.decorators.with_require_identity_authorization",
        _passthrough_decorator,
    ), patch(
        "inbound.flask.endpoints.prompts.with_require_identity_authorization",
        _passthrough_decorator,
    ):
        import importlib
        import inbound.flask.endpoints.prompts as prompts_mod
        prompts_mod.with_require_identity_authorization = _passthrough_decorator
        importlib.reload(prompts_mod)

        test_app = Flask(__name__)
        test_app.config["TESTING"] = True

        container = Mock()
        container.prompt_service = mock_prompt_service
        test_app.container = container

        test_app.register_blueprint(prompts_mod.prompts_bp, url_prefix="/api/prompts")

        @test_app.before_request
        def _inject_identity():
            from flask import g
            g.identity = identity

        yield test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ═══════════════════════════════════════════════════════════════════
# 6.1 POST /api/prompts/prompt.create
# ═══════════════════════════════════════════════════════════════════

class TestCreateEndpoint:
    def test_successful_creation(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity)
        mock_prompt_service.create.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.create",
            json={
                "blueprintId": "bp-1",
                "text": "Generate report",
                "schedule": {"interval": "PT900S"},
            },
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["blueprint_id"] == "bp-1"

    def test_blueprint_not_found(self, client, mock_prompt_service):
        mock_prompt_service.create.side_effect = BlueprintNotFoundError("bp-nope")
        resp = client.post(
            "/api/prompts/prompt.create",
            json={"blueprintId": "bp-nope", "text": "x", "schedule": {"interval": "PT60S"}},
        )
        assert resp.status_code == 404
        assert resp.get_json()["error_type"] == "BLUEPRINT_NOT_FOUND"

    def test_limit_exceeded(self, client, mock_prompt_service):
        mock_prompt_service.create.side_effect = PromptLimitExceededError("bp-1", 10)
        resp = client.post(
            "/api/prompts/prompt.create",
            json={"blueprintId": "bp-1", "text": "x", "schedule": {"interval": "PT60S"}},
        )
        assert resp.status_code == 409
        assert resp.get_json()["error_type"] == "LIMIT_EXCEEDED"

    def test_invalid_schedule(self, client, mock_prompt_service):
        mock_prompt_service.create.side_effect = ValueError("bad schedule")
        resp = client.post(
            "/api/prompts/prompt.create",
            json={"blueprintId": "bp-1", "text": "x", "schedule": {}},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_type"] == "VALIDATION_ERROR"

    def test_source_shortcut_copy(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity)
        mock_prompt_service.create.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.create",
            json={
                "blueprintId": "bp-1",
                "text": "x",
                "source": "shortcut_copy",
                "schedule": {"interval": "PT60S"},
            },
        )
        assert resp.status_code == 201
        assert mock_prompt_service.create.call_args[1]["source"] == "shortcut_copy"


# ═══════════════════════════════════════════════════════════════════
# 6.2 POST /api/prompts/prompt.update
# ═══════════════════════════════════════════════════════════════════

class TestUpdateEndpoint:
    def test_update_text(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity, text="new text")
        mock_prompt_service.update.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.update",
            json={"promptId": "p1", "text": "new text"},
        )
        assert resp.status_code == 200

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.update.side_effect = PromptNotFoundError("p1")
        resp = client.post(
            "/api/prompts/prompt.update",
            json={"promptId": "p1", "text": "x"},
        )
        assert resp.status_code == 404
        assert resp.get_json()["error_type"] == "NOT_FOUND"

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.update.side_effect = PromptPermissionError("p1", identity)
        resp = client.post(
            "/api/prompts/prompt.update",
            json={"promptId": "p1", "text": "x"},
        )
        assert resp.status_code == 403
        assert resp.get_json()["error_type"] == "FORBIDDEN"

    def test_validation_error(self, client, mock_prompt_service):
        mock_prompt_service.update.side_effect = ValueError("bad value")
        resp = client.post(
            "/api/prompts/prompt.update",
            json={"promptId": "p1", "schedule": {}},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_type"] == "VALIDATION_ERROR"


# ═══════════════════════════════════════════════════════════════════
# 6.3 GET /api/prompts/prompt.list
# ═══════════════════════════════════════════════════════════════════

class TestListEndpoint:
    def test_list_all_for_identity(self, client, mock_prompt_service):
        mock_prompt_service.list_enriched.return_value = [
            {"id": "p1", "blueprint_name": "BP 1", "run_stats": {}},
        ]
        resp = client.get("/api/prompts/prompt.list")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["blueprint_name"] == "BP 1"

    def test_filter_by_blueprint_id(self, client, mock_prompt_service):
        mock_prompt_service.list_enriched.return_value = []
        resp = client.get("/api/prompts/prompt.list?blueprintId=bp-123")
        assert resp.status_code == 200
        call_kwargs = mock_prompt_service.list_enriched.call_args[1]
        assert call_kwargs["blueprint_id"] == "bp-123"

    def test_empty_result(self, client, mock_prompt_service):
        mock_prompt_service.list_enriched.return_value = []
        resp = client.get("/api/prompts/prompt.list")
        assert resp.status_code == 200
        assert resp.get_json() == []


# ═══════════════════════════════════════════════════════════════════
# 6.4 GET /api/prompts/prompt.get
# ═══════════════════════════════════════════════════════════════════

class TestGetEndpoint:
    def test_get_existing(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity)
        mock_prompt_service.get.return_value = prompt
        resp = client.get(f"/api/prompts/prompt.get?promptId={prompt.id}")
        assert resp.status_code == 200

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.get.side_effect = PromptNotFoundError("p1")
        resp = client.get("/api/prompts/prompt.get?promptId=p1")
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.get.side_effect = PromptPermissionError("p1", identity)
        resp = client.get("/api/prompts/prompt.get?promptId=p1")
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6.5 POST /api/prompts/prompt.schedule.pause
# ═══════════════════════════════════════════════════════════════════

class TestPauseEndpoint:
    def test_pause_active(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity, status=ScheduleStatus.PAUSED)
        mock_prompt_service.pause.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.schedule.pause", json={"promptId": "p1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["schedule_status"] == "paused"

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.pause.side_effect = PromptNotFoundError("p1")
        resp = client.post(
            "/api/prompts/prompt.schedule.pause", json={"promptId": "p1"},
        )
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.pause.side_effect = PromptPermissionError("p1", identity)
        resp = client.post(
            "/api/prompts/prompt.schedule.pause", json={"promptId": "p1"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6.6 POST /api/prompts/prompt.schedule.resume
# ═══════════════════════════════════════════════════════════════════

class TestResumeEndpoint:
    def test_resume_paused(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity, status=ScheduleStatus.ACTIVE)
        mock_prompt_service.resume.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.schedule.resume", json={"promptId": "p1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["schedule_status"] == "active"

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.resume.side_effect = PromptNotFoundError("p1")
        resp = client.post(
            "/api/prompts/prompt.schedule.resume", json={"promptId": "p1"},
        )
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.resume.side_effect = PromptPermissionError("p1", identity)
        resp = client.post(
            "/api/prompts/prompt.schedule.resume", json={"promptId": "p1"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6.7 DELETE /api/prompts/prompt.delete
# ═══════════════════════════════════════════════════════════════════

class TestDeleteEndpoint:
    def test_delete_existing(self, client, mock_prompt_service):
        mock_prompt_service.delete.return_value = None
        resp = client.delete(
            "/api/prompts/prompt.delete", json={"promptId": "p1"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["deleted"] is True

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.delete.side_effect = PromptNotFoundError("p1")
        resp = client.delete(
            "/api/prompts/prompt.delete", json={"promptId": "p1"},
        )
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.delete.side_effect = PromptPermissionError("p1", identity)
        resp = client.delete(
            "/api/prompts/prompt.delete", json={"promptId": "p1"},
        )
        assert resp.status_code == 403


# ═══════════════════════════════════════════════════════════════════
# 6.8 POST /api/prompts/prompt.schedule.trigger
# ═══════════════════════════════════════════════════════════════════

class TestTriggerEndpoint:
    def test_trigger_active(self, client, mock_prompt_service, identity):
        prompt = _make_prompt(identity)
        mock_prompt_service.trigger.return_value = prompt
        resp = client.post(
            "/api/prompts/prompt.schedule.trigger", json={"promptId": "p1"},
        )
        assert resp.status_code == 200

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.trigger.side_effect = PromptNotFoundError("p1")
        resp = client.post(
            "/api/prompts/prompt.schedule.trigger", json={"promptId": "p1"},
        )
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.trigger.side_effect = PromptPermissionError("p1", identity)
        resp = client.post(
            "/api/prompts/prompt.schedule.trigger", json={"promptId": "p1"},
        )
        assert resp.status_code == 403

    def test_no_temporal_schedule(self, client, mock_prompt_service):
        mock_prompt_service.trigger.side_effect = ValueError("no active Temporal schedule")
        resp = client.post(
            "/api/prompts/prompt.schedule.trigger", json={"promptId": "p1"},
        )
        assert resp.status_code == 400
        assert resp.get_json()["error_type"] == "VALIDATION_ERROR"


# ═══════════════════════════════════════════════════════════════════
# 6.9 GET /api/prompts/prompt.runs
# ═══════════════════════════════════════════════════════════════════

class TestRunsEndpoint:
    def test_returns_sessions(self, client, mock_prompt_service):
        mock_prompt_service.get_runs.return_value = [
            ScheduleRunSummary(session_id="s1", status="completed"),
        ]
        resp = client.get("/api/prompts/prompt.runs?promptId=p1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["session_id"] == "s1"
        assert data[0]["status"] == "completed"

    def test_default_limit_20(self, client, mock_prompt_service):
        mock_prompt_service.get_runs.return_value = []
        client.get("/api/prompts/prompt.runs?promptId=p1")
        call_kwargs = mock_prompt_service.get_runs.call_args[1]
        assert call_kwargs["limit"] == 20

    def test_custom_limit(self, client, mock_prompt_service):
        mock_prompt_service.get_runs.return_value = []
        client.get("/api/prompts/prompt.runs?promptId=p1&limit=3")
        call_kwargs = mock_prompt_service.get_runs.call_args[1]
        assert call_kwargs["limit"] == 3

    def test_no_runs(self, client, mock_prompt_service):
        mock_prompt_service.get_runs.return_value = []
        resp = client.get("/api/prompts/prompt.runs?promptId=p1")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_not_found(self, client, mock_prompt_service):
        mock_prompt_service.get_runs.side_effect = PromptNotFoundError("p1")
        resp = client.get("/api/prompts/prompt.runs?promptId=p1")
        assert resp.status_code == 404

    def test_forbidden(self, client, mock_prompt_service, identity):
        mock_prompt_service.get_runs.side_effect = PromptPermissionError("p1", identity)
        resp = client.get("/api/prompts/prompt.runs?promptId=p1")
        assert resp.status_code == 403
