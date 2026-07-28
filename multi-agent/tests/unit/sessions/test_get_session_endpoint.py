"""Unit tests for GET /session.get (deep-link session retrieval).

Validates the HTTP-layer mapping of service exceptions to status codes:
- 200 for the owning identity
- 403 when SessionService raises PermissionError
- 404 when SessionService raises KeyError
- 500 for unexpected errors
"""
from unittest.mock import Mock, patch

import pytest
from flask import Flask

from mas.core.identity import Identity
from mas.session.domain.models import (
    SessionChat,
    SessionDetail,
    SessionMeta,
)


@pytest.fixture
def identity():
    return Identity.user("test-user")


def _make_detail(session_id="sess-1", blueprint_id="bp-1"):
    return SessionDetail(
        session_id=session_id,
        blueprint_id=blueprint_id,
        blueprint_name="My Blueprint",
        status="COMPLETED",
        meta=SessionMeta(),
        created_at=None,
        completed_at=None,
        chat=SessionChat(),
    )


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
def mock_session_service():
    return Mock()


@pytest.fixture
def app(mock_session_service, identity):
    with patch(
        "inbound.flask.decorators.with_require_identity_authorization",
        _passthrough_decorator,
    ), patch(
        "inbound.flask.endpoints.sessions.with_require_identity_authorization",
        _passthrough_decorator,
    ):
        import importlib
        import inbound.flask.endpoints.sessions as sessions_mod
        sessions_mod.with_require_identity_authorization = _passthrough_decorator
        importlib.reload(sessions_mod)

        test_app = Flask(__name__)
        test_app.config["TESTING"] = True

        container = Mock()
        container.session_service = mock_session_service
        test_app.container = container

        test_app.register_blueprint(
            sessions_mod.sessions_bp, url_prefix="/api/sessions",
        )

        @test_app.before_request
        def _inject_identity():
            from flask import g
            g.identity = identity

        yield test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ═══════════════════════════════════════════════════════════════════
# GET /api/sessions/session.get  —  200 / 403 / 404 / 500
# ═══════════════════════════════════════════════════════════════════

class TestGetSessionDetail:
    def test_owner_gets_200(self, client, mock_session_service):
        detail = _make_detail()
        mock_session_service.get_session_detail.return_value = detail

        resp = client.get("/api/sessions/session.get?sessionId=sess-1")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["sessionId"] == "sess-1"
        assert data["blueprintId"] == "bp-1"
        assert data["blueprintName"] == "My Blueprint"
        assert data["status"] == "COMPLETED"

    def test_non_owner_gets_403(self, client, mock_session_service):
        mock_session_service.get_session_detail.side_effect = PermissionError(
            "Session sess-1 not owned by other-user"
        )

        resp = client.get("/api/sessions/session.get?sessionId=sess-1")

        assert resp.status_code == 403
        data = resp.get_json()
        assert data["error_type"] == "FORBIDDEN"
        assert "not owned" in data["error"]

    def test_missing_session_gets_404(self, client, mock_session_service):
        mock_session_service.get_session_detail.side_effect = KeyError(
            "No session for sess-missing"
        )

        resp = client.get("/api/sessions/session.get?sessionId=sess-missing")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "not found" in data["error"]

    def test_unexpected_error_gets_500(self, client, mock_session_service):
        mock_session_service.get_session_detail.side_effect = RuntimeError(
            "db connection lost"
        )

        resp = client.get("/api/sessions/session.get?sessionId=sess-1")

        assert resp.status_code == 500
        data = resp.get_json()
        assert "db connection lost" in data["error"]

    def test_missing_session_id_param_gets_422(self, client):
        resp = client.get("/api/sessions/session.get")
        assert resp.status_code == 422
