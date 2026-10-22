"""Trust marker for ``X-Authenticated-User`` (shared secret or explicit dev mode)."""
from __future__ import annotations

import pytest
from flask import Flask, request

from global_utils.flask.decorators import validate_session
from global_utils.internal_auth import (
    internal_auth_headers,
    is_trusted_internal_request,
    trusted_header_user,
)

SECRET = "s3cret-value"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)


def test_forged_user_header_ignored_without_secret_configured():
    assert trusted_header_user({"X-Authenticated-User": "alice"}) is None


def test_forged_user_header_ignored_without_secret_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    assert trusted_header_user({"X-Authenticated-User": "alice"}) is None


def test_wrong_secret_rejected(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    headers = {"X-Authenticated-User": "alice", "X-Internal-Auth": "nope"}
    assert not is_trusted_internal_request(headers)
    assert trusted_header_user(headers) is None


def test_matching_secret_honours_user_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    headers = {"X-Authenticated-User": " alice ", "X-Internal-Auth": SECRET}
    assert trusted_header_user(headers) == "alice"


def test_dev_mode_honours_user_header(monkeypatch):
    monkeypatch.setenv("UNIFAI_DEV_MODE", "true")
    assert trusted_header_user({"X-Authenticated-User": "alice"}) == "alice"


def test_dev_mode_must_be_explicit_truthy(monkeypatch):
    monkeypatch.setenv("UNIFAI_DEV_MODE", "false")
    assert trusted_header_user({"X-Authenticated-User": "alice"}) is None


def test_outbound_headers_carry_secret_and_user(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    assert internal_auth_headers("bob") == {
        "X-Internal-Auth": SECRET,
        "X-Authenticated-User": "bob",
    }


def test_outbound_headers_without_secret_have_no_marker():
    assert internal_auth_headers("bob") == {"X-Authenticated-User": "bob"}


def _validate(headers):
    app = Flask(__name__)
    with app.test_request_context(headers=headers):
        return validate_session(
            get_redis_store=lambda: None,
            get_session_id=lambda: None,
            get_fallback_user=lambda: trusted_header_user(request.headers),
        )


def test_validate_session_rejects_forged_header():
    data, err = _validate({"X-Authenticated-User": "admin"})
    assert data is None and err[2] == 401


def test_validate_session_accepts_trusted_header(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    data, err = _validate({"X-Authenticated-User": "svc-user", "X-Internal-Auth": SECRET})
    assert err is None and data.username == "svc-user"
