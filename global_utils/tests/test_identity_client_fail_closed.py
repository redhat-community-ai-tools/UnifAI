"""``IdentityClient.is_member`` fails closed when the client is unconfigured."""
from __future__ import annotations

import pytest

from global_utils.identity_client import IdentityClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)


def test_unconfigured_client_denies_membership():
    assert IdentityClient(base_url="").is_member("alice", "team-1") is False


def test_unconfigured_client_allows_membership_in_explicit_dev_mode(monkeypatch):
    monkeypatch.setenv("UNIFAI_DEV_MODE", "true")
    assert IdentityClient(base_url="").is_member("alice", "team-1") is True


def test_configured_client_checks_team_ids(monkeypatch):
    c = IdentityClient(base_url="http://identity")
    monkeypatch.setattr(c, "get_team_ids", lambda _u: frozenset({"team-1"}))
    assert c.is_member("alice", "team-1") is True
    assert c.is_member("alice", "team-2") is False


def test_requests_carry_internal_secret(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", "s3cret")
    seen = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"teams": []}

    def fake_get(url, params=None, headers=None, timeout=None):
        seen.update(headers)
        return Resp()

    monkeypatch.setattr("global_utils.identity_client.http_requests.get", fake_get)
    IdentityClient(base_url="http://identity").list_teams_for_user("alice")
    assert seen["X-Internal-Auth"] == "s3cret"
