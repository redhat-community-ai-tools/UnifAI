"""Group-bound teams are honoured from Identity's own groups cache."""

from __future__ import annotations

import pytest
from flask import Flask

from adapters.inbound.flask.endpoints.team_routes import team_bp
from teams.models import Team, TeamMember, TeamMemberType
from teams.service import TeamService

pytestmark = pytest.mark.unit

SECRET = "s3cret-value"
GROUP = "agent_tekos"


@pytest.fixture(autouse=True)
def _reset_fake_stores(monkeypatch):
    """Shadow the conftest autouse fixture: no Flask app / Mongo needed."""
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)


class FakeRepo:
    """Mirrors MongoTeamRepository.find_by_member semantics."""

    def __init__(self):
        self.teams = {}

    def create(self, team):
        self.teams[team.team_id] = team

    def get(self, team_id):
        return self.teams[team_id]

    def find_by_name(self, name):
        return next((t for t in self.teams.values() if t.name == name), None)

    def update(self, team):
        self.teams[team.team_id] = team
        return team.team_id

    def find_by_member(self, member_id, group_ids=None):
        out = []
        for t in self.teams.values():
            for m in t.members:
                if m.type == TeamMemberType.USER and m.id == member_id:
                    out.append(t)
                    break
                if m.type == TeamMemberType.GROUP:
                    if group_ids is None and member_id in (m.group_members or []):
                        out.append(t)
                        break
                    if group_ids and m.id in group_ids:
                        out.append(t)
                        break
        return out


class FakeGroupsCache:
    def __init__(self):
        self.data = {}

    def get_groups(self, username):
        return self.data.get(username)


class FakeAuth:
    def __init__(self, username=None):
        self.username = username

    def is_authenticated(self):
        return self.username is not None

    def get_user_info(self):
        return {"username": self.username}

    def _check_admin_permission(self, user):
        return False


def _setup(session_user=None):
    repo, cache = FakeRepo(), FakeGroupsCache()
    svc = TeamService(repo, user_groups_cache=cache)
    team = Team(
        name="tekos",
        created_by="alice",
        members=[
            TeamMember(type=TeamMemberType.USER, id="alice", display_name="alice"),
            TeamMember(type=TeamMemberType.GROUP, id=GROUP, display_name=GROUP),
        ],
    )
    repo.create(team)
    app = Flask(__name__)
    app.extensions["team_service"] = svc
    app.extensions["auth_manager"] = FakeAuth(session_user)
    app.register_blueprint(team_bp, url_prefix="/api/teams")
    return app.test_client(), cache, team




def _service_headers():
    from global_utils.internal_auth import internal_auth_headers
    return internal_auth_headers()


def _ids(resp):
    assert resp.status_code == 200
    return [t["team_id"] for t in resp.get_json()["teams"]]


def _group(gid):
    return {"group_id": gid, "name": gid}


def test_service_call_sees_group_team_for_cached_group_member():
    client, cache, team = _setup()
    cache.data["bob"] = [_group(GROUP)]
    r = client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())
    assert _ids(r) == [team.team_id]


def test_service_call_without_cached_groups_keeps_user_members_only():
    client, cache, team = _setup()
    r = client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())
    assert _ids(r) == []


def test_service_call_for_user_lacking_the_group_sees_nothing():
    client, cache, team = _setup()
    cache.data["bob"] = [_group("other")]
    r = client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())
    assert _ids(r) == []


def test_service_explicit_group_ids_still_honoured():
    client, cache, team = _setup()
    r = client.get(f"/api/teams/teams.list?userId=bob&groupIds={GROUP}", headers=_service_headers())
    assert _ids(r) == [team.team_id]


def test_session_cannot_widen_with_fake_group_ids():
    client, cache, team = _setup("bob")
    cache.data["bob"] = [_group("other")]
    assert _ids(client.get(f"/api/teams/teams.list?groupIds={GROUP}")) == []


def test_session_cannot_inject_group_ids_without_cached_groups():
    client, cache, team = _setup("bob")
    assert _ids(client.get(f"/api/teams/teams.list?groupIds={GROUP}")) == []


def test_session_uses_cached_groups_and_may_narrow():
    client, cache, team = _setup("bob")
    cache.data["bob"] = [_group(GROUP)]
    assert _ids(client.get("/api/teams/teams.list")) == [team.team_id]
    assert _ids(client.get(f"/api/teams/teams.list?groupIds={GROUP}")) == [team.team_id]
    assert _ids(client.get("/api/teams/teams.list?groupIds=")) == []


def test_team_get_and_update_for_group_member():
    client, cache, team = _setup("bob")
    cache.data["bob"] = [_group(GROUP)]
    assert client.get(f"/api/teams/team.get?teamId={team.team_id}").status_code == 200


def test_team_get_denied_without_group_membership():
    client, cache, team = _setup("bob")
    assert client.get(f"/api/teams/team.get?teamId={team.team_id}").status_code == 404
    cache.data["bob"] = [_group("other")]
    assert client.get(f"/api/teams/team.get?teamId={team.team_id}").status_code == 404
    r = client.put("/api/teams/team.update", json={"teamId": team.team_id, "name": "x"})
    assert r.status_code == 404


def test_team_update_refused_for_a_mere_group_member():
    client, cache, team = _setup("bob")
    cache.data["bob"] = [_group(GROUP)]
    r = client.put("/api/teams/team.update", json={"teamId": team.team_id, "name": "renamed"})
    assert r.status_code == 403
    r = client.put("/api/teams/team.update", json={"teamId": team.team_id, "members": []})
    assert r.status_code == 403


def test_team_update_allowed_for_the_creator():
    client, cache, team = _setup("alice")
    r = client.put("/api/teams/team.update", json={"teamId": team.team_id, "name": "renamed"})
    assert r.status_code == 200


def test_team_update_allowed_for_the_trusted_service():
    client, cache, team = _setup()
    r = client.put(
        "/api/teams/team.update", json={"teamId": team.team_id, "name": "renamed"}, headers=_service_headers(),
    )
    assert r.status_code == 200


def test_team_delete_is_not_found_for_a_non_member_like_a_missing_team():
    client, cache, team = _setup("bob")
    missing = client.delete("/api/teams/team.delete?teamId=nope")
    denied = client.delete(f"/api/teams/team.delete?teamId={team.team_id}")
    assert denied.status_code == missing.status_code == 404
    assert denied.get_json() == missing.get_json()


def test_member_who_is_not_creator_cannot_delete():
    client, cache, team = _setup("bob")
    cache.data["bob"] = [_group(GROUP)]
    assert client.delete(f"/api/teams/team.delete?teamId={team.team_id}").status_code == 403


def test_create_refuses_a_group_the_caller_is_not_in():
    client, cache, team = _setup("mallory")
    cache.data["mallory"] = [_group("mine")]
    r = client.post("/api/teams/team.create", json={
        "name": "t1", "members": [{"type": "group", "id": "finance-admins", "display_name": "x"}],
    })
    assert r.status_code == 400


def test_create_drops_a_client_supplied_group_snapshot():
    client, cache, team = _setup("mallory")
    cache.data["mallory"] = [_group("mine")]
    r = client.post("/api/teams/team.create", json={
        "name": "t2",
        "members": [{"type": "group", "id": "mine", "display_name": "mine", "group_members": ["alice", "bob"]}],
    })
    assert r.status_code == 201
    group = [m for m in r.get_json()["members"] if m["type"] == "group"][0]
    assert group["group_members"] == []


def test_service_may_create_a_team_for_any_group():
    client, cache, team = _setup()
    r = client.post("/api/teams/team.create", headers=_service_headers(), json={
        "name": "t3", "createdBy": "operator",
        "members": [{"type": "group", "id": "agent_x", "display_name": "agent_x"}],
    })
    assert r.status_code == 201


def test_update_refuses_a_group_the_creator_is_not_in():
    client, cache, team = _setup("alice")
    cache.data["alice"] = [_group("mine")]
    r = client.put("/api/teams/team.update", json={
        "teamId": team.team_id, "members": [{"type": "group", "id": "finance-admins", "display_name": "x"}],
    })
    assert r.status_code == 400


def test_group_removal_after_cache_expiry_revokes_access():
    client, cache, team = _setup()
    cache.data["bob"] = [_group(GROUP)]
    assert _ids(client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())) == [team.team_id]
    cache.data["bob"] = [_group("other")]  # token refreshed without the group
    assert _ids(client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())) == []
    del cache.data["bob"]  # TTL expiry -> unknown -> user members only
    assert _ids(client.get("/api/teams/teams.list?userId=bob", headers=_service_headers())) == []
