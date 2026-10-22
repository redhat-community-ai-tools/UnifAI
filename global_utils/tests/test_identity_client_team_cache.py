"""IdentityClient team-id cache: TTL expiry and re-fetch on a miss."""
from __future__ import annotations

import pytest

from global_utils import identity_client
from global_utils.identity_client import IdentityClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)


class FakeHttp:
    def __init__(self):
        self.teams = []
        self.calls = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.calls.append((url, dict(params or {})))
        outer = self

        class Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"teams": list(outer.teams)}

        return Resp()


@pytest.fixture
def http(monkeypatch):
    fake = FakeHttp()
    monkeypatch.setattr(identity_client.http_requests, "get", fake.get)
    return fake


def test_membership_is_cached_then_refetched_on_miss(http):
    c = IdentityClient("http://identity")
    http.teams = [{"team_id": "t1", "name": "tekos"}]
    assert c.is_member("bob", "t1") is True
    assert c.is_member("bob", "t1") is True
    assert len(http.calls) == 1
    http.teams.append({"team_id": "t2", "name": "new"})
    assert c.is_member("bob", "t2") is True  # miss -> invalidate -> refetch
    assert len(http.calls) == 2


def test_revoked_membership_stops_after_ttl(http, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(identity_client.time, "monotonic", lambda: now[0])
    c = IdentityClient("http://identity")
    http.teams = [{"team_id": "t1"}]
    assert "t1" in c.get_team_ids("bob")
    http.teams = []
    assert "t1" in c.get_team_ids("bob")  # still within TTL
    now[0] += identity_client._TEAM_CACHE_TTL_SEC + 1
    assert c.get_team_ids("bob") == frozenset()


def test_denied_after_group_removal_via_is_member(http):
    c = IdentityClient("http://identity")
    http.teams = [{"team_id": "t1"}]
    assert c.is_member("bob", "t1")
    http.teams = []
    c._invalidate_cached_teams("bob")
    assert c.is_member("bob", "t1") is False
