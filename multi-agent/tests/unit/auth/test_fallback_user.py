"""``X-Authenticated-User`` is honoured only from trusted internal callers."""
import pytest
from flask import Flask

from inbound.flask.decorators import _get_fallback_user

pytestmark = pytest.mark.unit

SECRET = "s3cret-value"


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)


def _user(headers):
    with Flask(__name__).test_request_context(headers=headers):
        return _get_fallback_user()


def test_forged_header_ignored():
    assert _user({"X-Authenticated-User": "admin"}) is None


def test_forged_header_ignored_with_wrong_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    assert _user({"X-Authenticated-User": "admin", "X-Internal-Auth": "x"}) is None


def test_header_honoured_with_matching_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    assert _user({"X-Authenticated-User": "svc", "X-Internal-Auth": SECRET}) == "svc"


def test_header_honoured_in_dev_mode(monkeypatch):
    monkeypatch.setenv("UNIFAI_DEV_MODE", "1")
    assert _user({"X-Authenticated-User": "dev"}) == "dev"
