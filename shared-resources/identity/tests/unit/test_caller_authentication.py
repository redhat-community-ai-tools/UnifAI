"""Team, directory and identity routes require an authenticated caller."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from flask import Flask

from adapters.inbound.flask.endpoints.directory_routes import directory_bp
from adapters.inbound.flask.endpoints.identity_routes import identity_bp
from adapters.inbound.flask.endpoints.team_routes import team_bp
from teams.models import Team, TeamMember, TeamMemberType

pytestmark = pytest.mark.unit

SECRET = "s3cret-value"


@pytest.fixture(autouse=True)
def _reset_fake_stores(monkeypatch):
    """Shadow the conftest autouse fixture: these tests need no Flask app/Mongo."""
    monkeypatch.delenv("INTERNAL_AUTH_SECRET", raising=False)
    monkeypatch.delenv("UNIFAI_DEV_MODE", raising=False)


class FakeAuth:
    def __init__(self, username=None, admin=False):
        self.username, self.admin = username, admin

    def is_authenticated(self):
        return self.username is not None

    def get_user_info(self):
        return {"username": self.username}

    def _check_admin_permission(self, user):
        return self.admin


class FakeTeamService:
    has_directory = False

    def __init__(self):
        self.teams = {}
        self.created = []

    def create(self, name, created_by, members=None):
        self.created.append(created_by)
        team = Team(
            name=name,
            created_by=created_by,
            members=[TeamMember(type=TeamMemberType.USER, id=created_by, display_name=created_by)],
        )
        self.teams[team.team_id] = team
        return team

    def get(self, team_id):
        return self.teams[team_id]

    def list_user_teams(self, user_id, group_ids=None):
        return [t for t in self.teams.values() if any(m.id == user_id for m in t.members)]

    def update(self, team_id, name=None, members=None):
        team = self.teams[team_id]
        team.name = name or team.name
        return team

    def delete(self, team_id):
        del self.teams[team_id]


def make_client(username=None, admin=False, svc=None):
    app = Flask(__name__)
    app.extensions["team_service"] = svc or FakeTeamService()
    app.extensions["auth_manager"] = FakeAuth(username, admin)
    for bp, prefix in ((team_bp, "/api/teams"), (directory_bp, "/api/directory"), (identity_bp, "/api/identity")):
        app.register_blueprint(bp, url_prefix=prefix)
    return app.test_client(), app.extensions["team_service"]


ANON_REQUESTS = [
    ("post", "/api/teams/team.create", {"json": {"name": "t", "createdBy": "x"}}),
    ("get", "/api/teams/teams.list?userId=victim", {}),
    ("get", "/api/teams/team.get?teamId=1", {}),
    ("put", "/api/teams/team.update", {"json": {"teamId": "1", "name": "n"}}),
    ("delete", "/api/teams/team.delete?teamId=1&requestedBy=x", {}),
    ("get", "/api/directory/directory.search_users?q=a", {}),
    ("get", "/api/directory/directory.get_user?userId=a", {}),
    ("get", "/api/identity/identity.resolve?id=a", {}),
]


@pytest.mark.parametrize("method,url,kw", ANON_REQUESTS)
def test_anonymous_requests_are_refused(method, url, kw):
    client, _ = make_client()
    assert getattr(client, method)(url, **kw).status_code == 401


@pytest.mark.parametrize("method,url,kw", ANON_REQUESTS)
def test_forged_user_header_does_not_authenticate(method, url, kw):
    client, _ = make_client()
    kw = {**kw, "headers": {"X-Authenticated-User": "admin"}}
    assert getattr(client, method)(url, **kw).status_code == 401


def test_created_by_comes_from_session_not_body():
    client, svc = make_client("alice")
    r = client.post("/api/teams/team.create", json={"name": "t", "createdBy": "mallory"})
    assert r.status_code == 201
    assert svc.created == ["alice"]


def test_teams_list_defaults_to_own_and_refuses_others():
    client, svc = make_client("alice")
    svc.create("mine", "alice")
    svc.create("theirs", "bob")
    names = [t["name"] for t in client.get("/api/teams/teams.list").get_json()["teams"]]
    assert names == ["mine"]
    assert client.get("/api/teams/teams.list?userId=bob").status_code == 403


def test_admin_can_list_other_users_teams():
    client, svc = make_client("root", admin=True)
    svc.create("theirs", "bob")
    assert len(client.get("/api/teams/teams.list?userId=bob").get_json()["teams"]) == 1


def test_non_member_cannot_read_update_or_delete():
    client, svc = make_client("mallory")
    team = svc.create("t", "alice")
    assert client.get(f"/api/teams/team.get?teamId={team.team_id}").status_code == 404
    r = client.put("/api/teams/team.update", json={"teamId": team.team_id, "name": "x"})
    assert r.status_code == 404
    r = client.delete(f"/api/teams/team.delete?teamId={team.team_id}&requestedBy=alice")
    assert r.status_code in (403, 404)
    assert team.team_id in svc.teams and svc.teams[team.team_id].name == "t"


def test_member_can_update_but_only_creator_can_delete():
    client, svc = make_client("bob")
    team = svc.create("t", "alice")
    team.members.append(TeamMember(type=TeamMemberType.USER, id="bob", display_name="bob"))
    assert client.put("/api/teams/team.update", json={"teamId": team.team_id, "name": "x"}).status_code == 200
    r = client.delete(f"/api/teams/team.delete?teamId={team.team_id}&requestedBy=alice")
    assert r.status_code == 403


def test_creator_can_delete_own_team():
    client, svc = make_client("alice")
    team = svc.create("t", "alice")
    assert client.delete(f"/api/teams/team.delete?teamId={team.team_id}").status_code == 200
    assert team.team_id not in svc.teams


def test_service_caller_with_matching_secret_is_accepted(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    client, svc = make_client()
    svc.create("t", "bob")
    r = client.get("/api/teams/teams.list?userId=bob", headers={"X-Internal-Auth": SECRET})
    assert r.status_code == 200 and len(r.get_json()["teams"]) == 1


def test_service_caller_with_wrong_secret_is_refused(monkeypatch):
    monkeypatch.setenv("INTERNAL_AUTH_SECRET", SECRET)
    client, _ = make_client()
    r = client.get("/api/teams/teams.list?userId=bob", headers={"X-Internal-Auth": "bad"})
    assert r.status_code == 401


def test_identity_resolve_accepts_session():
    client, _ = make_client("alice")
    assert client.get("/api/identity/identity.resolve?id=alice").status_code == 200
