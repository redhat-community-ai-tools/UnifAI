"""
Functional unit tests: OAuth login/callback, session-backed ``/api/auth/*`` routes.

Keycloak and Redis are faked in ``tests.conftest`` (``KEYCLOAK_MOCK`` + ``FAKE_REDIS``).
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from flask import redirect
from tests.conftest import FAKE_REDIS, KEYCLOAK_MOCK, login_client, valid_session_data

pytestmark = pytest.mark.unit


class TestLoginRoute:
    def test_login_rejects_request_without_state(self, client) -> None:
        r = client.get("/api/auth/login")
        assert r.status_code == 400
        j = r.get_json()
        assert j is not None
        assert j.get("error") == "State parameter is required"

    def test_login_redirects_to_idp_with_state(self, client) -> None:
        def _redir(redirect_uri, state=None, **kwargs):  # noqa: ARG001
            return redirect("https://idp.test/oauth/authorize?state=echo", code=302)

        KEYCLOAK_MOCK.authorize_redirect.side_effect = _redir
        r = client.get("/api/auth/login?state=abc123", follow_redirects=False)
        assert r.status_code == 302
        assert r.location.startswith("https://idp.test/")


class TestCallbackRoute:
    def test_callback_success_stores_session_and_redirects(self, client) -> None:
        """Uses ``FRONTEND_URL`` from the test process env (see ``tests/conftest``)."""
        import os
        import time

        ex = int(time.time()) + 3600
        KEYCLOAK_MOCK.authorize_access_token.return_value = {
            "access_token": "at-1",
            "refresh_token": "rt-1",
            "expires_at": ex,
        }
        KEYCLOAK_MOCK.userinfo.return_value = {
            "preferred_username": "cb_user",
            "email": "cb@example.com",
            "name": "Callback User",
            "sub": "sub-cb-1",
        }
        st = "eyJvcmlnaW5hbFVybCI6Ii8ifQ"  # passed through in redirect
        r = client.get(f"/api/auth/callback?code=auth-code&state={st}", follow_redirects=False)
        assert r.status_code == 302, r.data
        loc = r.location or ""
        fe = os.environ.get("FRONTEND_URL", "http://127.0.0.1:5000")
        assert "auth=success" in loc
        fe_norm = fe.rstrip("/")
        assert loc.startswith(fe_norm) or f"{fe_norm}/" in loc
        user_r = client.get("/api/auth/user", follow_redirects=True)
        assert user_r.status_code == 200
        u = (user_r.get_json() or {}).get("user") or {}
        assert u.get("username") == "cb_user"

    def test_callback_on_authlib_error_redirects_to_frontend_error(
        self, client, monkeypatch
    ) -> None:
        from authlib.common.errors import AuthlibBaseError

        from utils import auth_manager as am

        monkeypatch.setattr(am.config, "frontend_url", "http://error.test", raising=False)
        KEYCLOAK_MOCK.authorize_access_token.side_effect = AuthlibBaseError("oidc failed")
        r = client.get("/api/auth/callback?code=x&state=y", follow_redirects=False)
        assert r.status_code == 302
        assert "auth=error" in (r.location or "")
        assert (r.location or "").startswith("http://error.test")


class TestUserAndLogout:
    def test_get_user_returns_401_when_unauthenticated(self, client) -> None:
        r = client.get("/api/auth/user")
        assert r.status_code == 401
        assert r.get_json() is not None
        assert "error" in (r.get_json() or {})

    def test_get_user_returns_profile_when_authenticated(self, client) -> None:
        sid = "test-session-uuid-001"
        login_client(client, sid, valid_session_data(username="Alice"))
        r = client.get("/api/auth/user")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("authenticated") is True
        assert data.get("user", {}).get("username") == "Alice"
        assert "is_admin" in (data.get("user") or {})

    def test_logout_clears_session_in_redis(self, client) -> None:
        sid = "logout-session-001"
        login_client(client, sid, valid_session_data())
        assert FAKE_REDIS.hget(sid) != {}
        r = client.post("/api/auth/logout")
        assert r.status_code == 200
        # Redis key removed or session id cleared; implementation deletes redis key
        # when session has session_id
        assert FAKE_REDIS.hget(sid) == {}


class TestTokenRefresh:
    def test_refresh_requires_valid_session_in_redis(self, client) -> None:
        r = client.post("/api/auth/refresh")
        # No cookie session: no server-side user / refresh in Redis
        assert r.status_code == 401
        assert "refresh" in (r.get_json() or {}).get("error", "").lower()

    def test_refresh_401_without_refresh_token_in_server_session(self, client) -> None:
        sid = "s-no-rt"
        d = valid_session_data()
        d.pop("refresh_token", None)  # type: ignore[typeddict-ignored]
        FAKE_REDIS.hset(sid, d)
        with client.session_transaction() as sess:  # type: ignore[union-attr]
            sess["session_id"] = sid
        r = client.post("/api/auth/refresh")
        # Route returns 401 when no refresh in stored session
        assert r.status_code == 401


def test_expired_server_session_get_user_returns_401(client) -> None:
    sid = "expired-1"
    d = valid_session_data()
    d["session_expires_at"] = (datetime.now() - timedelta(hours=1)).timestamp()
    FAKE_REDIS.hset(sid, d)
    with client.session_transaction() as sess:  # type: ignore[union-attr]
        sess["session_id"] = sid
    r = client.get("/api/auth/user")
    assert r.status_code == 401


def test_protected_user_profile_requires_auth(client) -> None:
    r = client.get("/api/protected/user.profile")
    assert r.status_code == 401


def test_protected_user_profile_allows_authenticated_user(client) -> None:
    login_client(client, "prot-1", valid_session_data(username="p_user"))
    r = client.get("/api/protected/user.profile")
    assert r.status_code == 200
    j = r.get_json()
    assert "profile" in j
    assert j.get("message")


class TestAuthConfig:
    def test_auth_config_returns_local_auth_false_by_default(self, client, monkeypatch) -> None:
        from utils import auth_manager as am

        monkeypatch.setattr(am.config, "local_auth_enabled", False, raising=False)
        r = client.get("/api/auth/config")
        assert r.status_code == 200
        assert r.get_json() == {"local_auth": False}

    def test_auth_config_returns_local_auth_true(self, client, monkeypatch) -> None:
        from utils import auth_manager as am

        monkeypatch.setattr(am.config, "local_auth_enabled", True, raising=False)
        r = client.get("/api/auth/config")
        assert r.status_code == 200
        assert r.get_json() == {"local_auth": True}


class TestLocalAuth:
    """Exercises the full auth flow through ``DevOAuthClient``."""

    def _login_dev_user(self, client, identity_app):
        """Perform a dev-user login through the callback route and return the client."""
        from utils.dev_oauth_client import DevOAuthClient

        auth_mgr = identity_app.extensions["auth_manager"]
        auth_mgr.keycloak_client = DevOAuthClient()

        state = "eyJ0ZXN0IjoiZGV2In0"
        r = client.get(f"/api/auth/callback?code=dev-code&state={state}", follow_redirects=False)
        assert r.status_code == 302, r.data
        assert "auth=success" in (r.location or "")
        return client

    def test_login_redirects_to_callback_with_dev_code(self, client, identity_app) -> None:
        from utils.dev_oauth_client import DevOAuthClient

        auth_mgr = identity_app.extensions["auth_manager"]
        auth_mgr.keycloak_client = DevOAuthClient()

        r = client.get("/api/auth/login?state=test123", follow_redirects=False)
        assert r.status_code == 302
        loc = r.location or ""
        assert "code=dev-code" in loc
        assert "state=test123" in loc

    def test_callback_creates_dev_user_session(self, client, identity_app) -> None:
        self._login_dev_user(client, identity_app)
        r = client.get("/api/auth/user")
        assert r.status_code == 200
        user = (r.get_json() or {}).get("user", {})
        assert user.get("username") == "dev-user"
        assert user.get("email") == "dev@local.dev"

    def test_get_user_returns_dev_user_profile(self, client, identity_app) -> None:
        self._login_dev_user(client, identity_app)
        r = client.get("/api/auth/user")
        assert r.status_code == 200
        data = r.get_json()
        assert data.get("authenticated") is True
        user = data.get("user", {})
        assert user.get("name") == "Dev User"
        assert user.get("sub") == "local:dev-user"

    def test_logout_clears_dev_session(self, client, identity_app) -> None:
        self._login_dev_user(client, identity_app)
        r = client.get("/api/auth/user")
        assert r.status_code == 200

        r = client.post("/api/auth/logout")
        assert r.status_code == 200

        r = client.get("/api/auth/user")
        assert r.status_code == 401

    def test_refresh_succeeds_for_dev_session(self, client, identity_app) -> None:
        self._login_dev_user(client, identity_app)
        r = client.post("/api/auth/refresh")
        assert r.status_code == 200
        assert (r.get_json() or {}).get("message") == "Token refreshed successfully"


class TestRefreshTokenSuccess:
    def test_post_refresh_succeeds_when_keycloak_accepts(
        self, client, identity_app, monkeypatch
    ) -> None:
        sid = "refresh-ok-1"
        d = valid_session_data()
        FAKE_REDIS.hset(sid, d)
        with client.session_transaction() as sess:  # type: ignore[union-attr]
            sess["session_id"] = sid

        def _refresh_ok() -> bool:
            new_d = {**d, "access_token": "new-at", "token_expires_at": d["token_expires_at"]}
            FAKE_REDIS.hset(sid, new_d, ttl_seconds=60)
            return True

        auth_mgr = identity_app.extensions["auth_manager"]
        monkeypatch.setattr(auth_mgr, "_refresh_access_token", _refresh_ok)
        r = client.post("/api/auth/refresh")
        assert r.status_code == 200
        assert (r.get_json() or {}).get("message") == "Token refreshed successfully"
        assert FAKE_REDIS.hget(sid).get("access_token") == "new-at"
