"""The CLI login hands a signed session cookie to its callback: only to a local listener."""

from __future__ import annotations

import base64
import json
from unittest.mock import Mock

import pytest
from flask import Flask

from utils.auth_manager import AuthManager, is_loopback_callback

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _reset_fake_stores():
    """Shadow the conftest autouse fixture: nothing here needs Mongo or Redis."""


def _cli_state(callback_url) -> str:
    return base64.b64encode(json.dumps({"cli": True, "callbackUrl": callback_url}).encode()).decode()


@pytest.mark.parametrize("url", [
    "http://localhost:8765/callback",
    "http://127.0.0.1:8765/callback",
    "http://[::1]:8765/callback",
])
def test_loopback_targets_are_accepted(url):
    assert is_loopback_callback(url)


@pytest.mark.parametrize("url", [
    "https://evil.example/callback",
    "http://evil.example/callback",
    "http://localhost@evil.example/callback",
    "http://localhost:80@evil.example/",
    "https://localhost/callback",
    "http://localhost.evil.example/callback",
    "//evil.example/callback",
    "javascript:alert(1)",
    "",
    None,
    42,
])
def test_remote_or_malformed_targets_are_refused(url):
    assert not is_loopback_callback(url)


@pytest.fixture
def client():
    app = Flask(__name__)
    app.secret_key = "s"
    manager = AuthManager.__new__(AuthManager)
    manager.app = app
    manager.keycloak_client = Mock()
    manager.redis_store = Mock()
    manager._register_auth_routes()
    return app.test_client(), manager


def test_login_refuses_a_remote_cli_callback(client):
    c, manager = client
    r = c.get(f"/api/auth/login?state={_cli_state('https://evil.example/cb')}")
    assert r.status_code == 400
    manager.keycloak_client.authorize_redirect.assert_not_called()


def test_callback_never_redirects_a_session_to_a_remote_cli_callback(client):
    c, manager = client
    r = c.get(f"/api/auth/callback?code=c&state={_cli_state('https://evil.example/cb')}")
    assert r.status_code == 400
    assert "evil.example" not in (r.location or "")
    manager.redis_store.hset.assert_not_called()
