"""
Global test configuration and fixtures for the identity service (pytest).

Path setup mirrors RAG: ``pyproject`` adds the identity package and ``global_utils`` to
``pythonpath``; this file also prepends for environments that do not use ``pytest.ini``.

Run (from ``shared-resources/identity``)::

    pip install -e ../../global_utils/ -e ".[dev]"
    pytest tests/ -q

Functional tests use an in-memory Redis stand-in and a Keycloak client mock; no real
network or broker is required. Optional smoke tests under ``tests/smoke/`` need
``IDENTITY_SMOKE_URL`` (see that module).
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest import mock
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from flask import Flask

# -----------------------------------------------------------------------------
# Project paths (RAG-style)
# -----------------------------------------------------------------------------
_IDENTITY_ROOT = os.path.dirname(os.path.dirname(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_IDENTITY_ROOT, "..", ".."))
_GLOBAL_UTILS_SRC = os.path.join(_REPO_ROOT, "global_utils", "src")
for _p in (_IDENTITY_ROOT, _GLOBAL_UTILS_SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Keycloak / app env **before** the real ``import bootstrap.flask_app`` in the session fixture
os.environ.setdefault("KEYCLOAK_BASE_URL", "https://keycloak.test/auth")
os.environ.setdefault("CLIENT_ID", "identity-test-client")
os.environ.setdefault("CLIENT_SECRET", "identity-test-secret")
os.environ.setdefault("KEYCLOAK_REALM", "testrealm")
os.environ.setdefault("FRONTEND_URL", "http://127.0.0.1:5000")
os.environ.setdefault("BACKEND_ENV", "development")
os.environ["PYTEST_IDENTITY"] = "1"


# -----------------------------------------------------------------------------
# In-memory Redis stand-in
# -----------------------------------------------------------------------------


class InMemoryRedisStore:
    """Mimic :class:`global_utils.redis.RedisKVStore` hash session storage."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, Any]] = {}

    def clear(self) -> None:
        self._hashes.clear()

    def ping(self) -> bool:
        return True

    def hget(self, key: str) -> dict[str, Any]:
        h = self._hashes.get(key, {})
        return {k: self._coerce_get(v) for k, v in h.items()}

    @staticmethod
    def _coerce_get(v: Any) -> Any:
        if isinstance(v, (int, float)):
            return v
        if isinstance(v, str):
            return v
        if isinstance(v, bytes):
            return v.decode("utf-8", errors="replace")
        return v

    def hset(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        self._hashes[key] = dict(value)

    def delete(self, key: str) -> None:
        self._hashes.pop(key, None)


# Patched into ``build_redis_store``; **cleared between function-scoped tests**
FAKE_REDIS = InMemoryRedisStore()
# Returned by ``OAuth.register``; tests can adjust per scenario
KEYCLOAK_MOCK: mock.MagicMock = mock.MagicMock(name="keycloak_client")


# -----------------------------------------------------------------------------
# Flask app (one session, built with patches *held* until after ``create_app``)
# -----------------------------------------------------------------------------


@pytest.fixture(scope="session")
def identity_app() -> "Flask":
    p_redis = patch("bootstrap.factories.build_redis_store", return_value=FAKE_REDIS)
    p_oauth = patch(
        "authlib.integrations.flask_client.OAuth.register", return_value=KEYCLOAK_MOCK
    )
    p_redis.start()
    p_oauth.start()
    try:
        from config.app_config import AppConfig

        AppConfig.get_instance.cache_clear()
        import bootstrap.flask_app as m

        m.app.config["TESTING"] = True
        m.app.secret_key = b"test-secret-constant-32b-for-pytest-identity"
        return m.app
    finally:
        p_redis.stop()
        p_oauth.stop()


@pytest.fixture
def client(identity_app: "Flask"):
    """``Flask.test_client`` against the session-scoped app."""
    return identity_app.test_client()


@pytest.fixture(autouse=True)
def _reset_fake_stores(identity_app: "Flask") -> None:  # noqa: ARG001
    """Isolated in-memory data and a clean Keycloak client mock for each test."""
    FAKE_REDIS.clear()
    KEYCLOAK_MOCK.reset_mock()
    KEYCLOAK_MOCK.authorize_redirect = mock.MagicMock()
    KEYCLOAK_MOCK.authorize_access_token = mock.MagicMock()
    KEYCLOAK_MOCK.userinfo = mock.MagicMock()
    KEYCLOAK_MOCK.fetch_access_token = mock.MagicMock()
    yield
    FAKE_REDIS.clear()


# -----------------------------------------------------------------------------
# Helpers: seed Redis + Flask client session
# -----------------------------------------------------------------------------


def valid_session_data(**overrides: Any) -> dict[str, Any]:
    """Typical server-side session document stored in Redis (keys match AuthManager)."""
    now = datetime.now().timestamp()
    data = {
        "username": "testuser",
        "email": "testuser@example.com",
        "name": "Test User",
        "sub": "oidc-sub-testuser",
        "session_created_at": now,
        "session_expires_at": (datetime.now() + timedelta(hours=2)).timestamp(),
        "token_expires_at": (datetime.now() + timedelta(hours=1)).timestamp(),
        "access_token": "access-test-token",
        "refresh_token": "refresh-test-token",
    }
    data.update(overrides)
    return data


def login_client(
    test_client, session_id: str, session_data: dict[str, Any] | None = None
) -> None:
    """
    Set Flask session cookie and Redis payload so protected routes can resolve the user.
    """
    FAKE_REDIS.hset(session_id, session_data or valid_session_data())
    with test_client.session_transaction() as sess:  # type: ignore[union-attr]
        sess["session_id"] = session_id
        sess.permanent = True


# -----------------------------------------------------------------------------
# Markers (RAG-style)
# -----------------------------------------------------------------------------


def pytest_collection_modifyitems(config, items) -> None:  # noqa: ARG001
    for item in items:
        try:
            p = str(item.path)
        except AttributeError:
            p = str(getattr(item, "fspath", ""))
        if "/unit/" in p or "\\unit\\" in p:
            item.add_marker(pytest.mark.unit)
        if "/smoke/" in p or "\\smoke\\" in p:
            item.add_marker(pytest.mark.smoke)


def pytest_configure(config) -> None:  # noqa: ARG001
    config.addinivalue_line(
        "markers",
        "smoke: optional — may require a running service URL (see the smoke test module).",
    )

