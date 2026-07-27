"""Unit tests: health and version under ``/api/health/`` (no auth)."""

import pytest

pytestmark = pytest.mark.unit


class TestHealthEndpoints:
    def test_health_root_returns_ok(self, client) -> None:
        resp = client.get("/api/health/")
        assert resp.status_code == 200
        body = resp.get_json()
        assert body is not None
        assert body.get("status") == "ok"
        assert "message" in body

    def test_health_version_returns_configured_version(self, identity_app, client) -> None:
        identity_app.version = "9.8.7"
        resp = client.get("/api/health/version")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data == {"version": "9.8.7"}

