"""Object-level access on session, collaboration and workspace routes."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from inbound.flask.endpoints.collaboration.presence import collaboration_bp
from inbound.flask.endpoints.sessions import sessions_bp
from inbound.flask.endpoints.workspace import workspace_bp
from mas.core.identity import Identity, IdentityType

USER_A = Identity(type=IdentityType.USER, id="alice")
TEAM_T = Identity(type=IdentityType.TEAM, id="team-1")

SESSIONS = {
    "s-alice": USER_A,
    "s-team": TEAM_T,
}
TEAM_MEMBERS = {"team-1": {"carol"}}
ADMINS = {"root"}


class FakeSessionRepo:
    def fetch(self, run_id):
        if run_id not in SESSIONS:
            raise KeyError(run_id)
        return SimpleNamespace(identity=SESSIONS[run_id], run_id=run_id)

    def list_runs(self, identity):
        return [sid for sid, owner in SESSIONS.items() if owner == identity]

    def delete_by_identity(self, identity):
        return 1


class FakeIdentityProvider:
    def is_member(self, username, team_id):
        return username in TEAM_MEMBERS.get(team_id, set())

    def get_team_ids(self, username):
        return frozenset(t for t, m in TEAM_MEMBERS.items() if username in m)

    def resolve_team_display_name(self, username, team_id):
        return team_id


def _blueprint_doc(owner, metadata=None):
    return SimpleNamespace(identity=owner, metadata=metadata or {})


BLUEPRINTS = {
    "bp-alice": _blueprint_doc(USER_A),
    "bp-team": _blueprint_doc(TEAM_T),
    "bp-public": _blueprint_doc(USER_A, {"usageScope": "public"}),
}


class FakeBlueprintService:
    def get_blueprint_draft_doc(self, blueprint_id):
        if blueprint_id not in BLUEPRINTS:
            raise KeyError(blueprint_id)
        return BLUEPRINTS[blueprint_id]


@pytest.fixture
def env(monkeypatch):
    app = Flask(__name__)
    app.config["admin_allowed_users"] = list(ADMINS)
    for bp in (sessions_bp, collaboration_bp, workspace_bp):
        app.register_blueprint(bp)

    session_service = MagicMock()
    session_service.get_status.return_value = "IDLE"
    session_service.create.return_value = "new-run"
    session_service.get_state.return_value = {"ok": True}
    session_service.cancel.return_value = True
    session_service.delete.return_value = True
    session_service.get_meta.return_value = SimpleNamespace(
        hitl_overrides=None, model_dump=lambda mode="json": {"title": "t"},
    )
    session_service.update_meta.return_value = SimpleNamespace(
        model_dump=lambda mode="json": {"title": "x"},
    )
    monitor = MagicMock()
    monitor.is_available.return_value = True
    monitor.list_active.return_value = ["s-alice", "s-team", "s-other", "gone"]
    monitor.get_status.return_value = {"state": "x"}
    channel_factory = MagicMock()
    channel_factory.create_monitor.return_value = monitor
    collab = MagicMock()
    collab.is_available.return_value = True
    repo = FakeSessionRepo()
    resource_repo = MagicMock()
    resource_repo.delete_by_identity.return_value = 0
    blueprint_repo = MagicMock()
    blueprint_repo.delete_by_identity.return_value = 0
    app.container = SimpleNamespace(
        session_repo=repo,
        session_service=session_service,
        identity_provider=FakeIdentityProvider(),
        blueprint_service=FakeBlueprintService(),
        channel_factory=channel_factory,
        collaboration_service=collab,
        admin_config_reader=None,
        resource_repo=resource_repo,
        blueprint_repo=blueprint_repo,
        overrides_store=None,
    )
    SESSIONS["s-other"] = Identity(type=IdentityType.USER, id="bob")

    def fake_validate(get_store, get_sid, get_fallback):
        user = get_fallback()
        if not user:
            return None, ("Authentication required", "AUTHENTICATION_REQUIRED", 401)
        return SimpleNamespace(username=user), None

    monkeypatch.setattr("inbound.flask.decorators.validate_session", fake_validate)
    return app, app.test_client(), session_service, collab


def _h(user):
    return {"X-Authenticated-User": user}


# (method, path, kwargs builder) for every route addressed by a session id.
def _calls(sid):
    q = {"query_string": {"sessionId": sid}}
    b = lambda extra=None: {"json": {"sessionId": sid, **(extra or {})}}
    return {
        "cancel": ("post", "/session.cancel", b()),
        "delete": ("delete", "/session.delete", q),
        "state": ("get", "/session.state.get", q),
        "chat": ("get", "/session.chat.get", q),
        "status": ("get", "/session.status.get", q),
        "subscribe": ("get", "/session.subscribe", q),
        "stream_status": ("get", "/session.stream.status", q),
        "execute": ("post", "/user.session.execute", b({"inputs": {}})),
        "submit": ("post", "/user.session.submit", b({"inputs": {}})),
        "approval": ("post", "/session.approval",
                     b({"requestId": "r", "decision": "approve"})),
        "approval_rule": ("post", "/session.approval.rule", b({"action": "clear"})),
        "approval_rules": ("get", "/session.approval.rules", q),
        "meta_get": ("get", "/session.meta", q),
        "meta_post": ("post", "/session.meta", b({"meta": {"title": "x"}})),
        "join": ("post", "/session.join", b()),
        "leave": ("post", "/session.leave", b()),
        "heartbeat": ("post", "/session.heartbeat", b()),
        "typing_set": ("post", "/session.typing", b()),
        "typing_get": ("get", "/session.typing", q),
        "participants": ("get", "/session.participants", q),
    }


ROUTES = list(_calls("x"))


def _call(client, name, sid, user, extra_json=None):
    method, path, kw = _calls(sid)[name]
    kw = dict(kw)
    kw["headers"] = _h(user)
    if extra_json and "json" in kw:
        kw["json"] = {**kw["json"], **extra_json}
    return getattr(client, method)(path, **kw)


@pytest.mark.parametrize("route", ROUTES)
def test_owner_is_allowed(env, route):
    _, client, *_ = env
    resp = _call(client, route, "s-alice", "alice")
    assert resp.status_code != 404 or route == "stream_status", resp.get_json()
    assert resp.status_code not in (401, 403)


@pytest.mark.parametrize("route", ROUTES)
def test_other_user_gets_the_same_response_as_unknown_session(env, route):
    _, client, *_ = env
    denied = _call(client, route, "s-alice", "mallory")
    missing = _call(client, route, "does-not-exist", "mallory")
    assert denied.status_code == 404
    assert denied.status_code == missing.status_code
    assert denied.get_json() == missing.get_json()


@pytest.mark.parametrize("route", ROUTES)
def test_team_member_is_allowed(env, route):
    _, client, *_ = env
    resp = _call(client, route, "s-team", "carol")
    assert resp.status_code not in (401, 403)
    assert not (resp.status_code == 404 and resp.get_json() == {"error": "Session not found"})


@pytest.mark.parametrize("route", ROUTES)
def test_non_member_of_team_is_denied(env, route):
    _, client, *_ = env
    resp = _call(client, route, "s-team", "mallory")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Session not found"}


@pytest.mark.parametrize("route", ["cancel", "delete", "state", "meta_post", "join"])
def test_denied_call_has_no_side_effect(env, route):
    _, client, svc, collab = env
    _call(client, route, "s-alice", "mallory")
    svc.cancel.assert_not_called()
    svc.delete.assert_not_called()
    svc.get_state.assert_not_called()
    svc.update_meta.assert_not_called()
    collab.join_session.assert_not_called()


def test_unauthenticated_call_is_rejected(env):
    _, client, *_ = env
    resp = client.get("/session.state.get", query_string={"sessionId": "s-alice"})
    assert resp.status_code in (401, 403)


def test_meta_post_ignores_other_users_typing(env):
    _, client, svc, collab = env
    collab.get_typing_users.return_value = ["bob"]
    resp = _call(client, "meta_post", "s-alice", "alice",
                 {"meta": {"typing_users": ["alice", "bob"]}})
    assert resp.status_code == 200
    collab.set_typing.assert_called_once_with(session_id="s-alice", user_id="alice")
    collab.clear_typing.assert_not_called()


def test_stream_active_is_filtered_for_regular_user(env):
    _, client, *_ = env
    resp = client.get("/session.stream.active", headers=_h("alice"))
    assert resp.get_json()["active_sessions"] == ["s-alice"]


def test_stream_active_includes_team_sessions_for_members(env):
    _, client, *_ = env
    resp = client.get("/session.stream.active", headers=_h("carol"))
    assert resp.get_json()["active_sessions"] == ["s-team"]


def test_stream_active_admin_sees_all(env):
    _, client, *_ = env
    resp = client.get("/session.stream.active", headers=_h("root"))
    assert resp.get_json()["count"] == 4


def test_stream_active_requires_authentication(env):
    _, client, *_ = env
    assert client.get("/session.stream.active").status_code in (401, 403)


# ---- user.session.create ----

def _create(client, user, blueprint_id, **extra):
    return client.post("/user.session.create", headers=_h(user),
                       json={"blueprintId": blueprint_id, **extra})


def test_create_on_own_blueprint(env):
    _, client, svc, _ = env
    assert _create(client, "alice", "bp-alice").status_code == 200
    svc.create.assert_called_once()


def test_create_on_other_users_blueprint_is_denied_like_missing(env):
    _, client, svc, _ = env
    denied = _create(client, "mallory", "bp-alice")
    missing = _create(client, "mallory", "nope")
    assert denied.status_code == 404
    assert denied.get_json()["error_type"] == missing.get_json()["error_type"]
    svc.create.assert_not_called()


def test_create_on_team_blueprint(env):
    _, client, svc, _ = env
    assert _create(client, "carol", "bp-team").status_code == 200
    assert _create(client, "mallory", "bp-team").status_code == 404
    assert svc.create.call_count == 1


def test_create_on_public_blueprint_by_anyone(env):
    _, client, svc, _ = env
    assert _create(client, "mallory", "bp-public").status_code == 200
    svc.create.assert_called_once()


def test_create_admin_may_use_any_blueprint(env):
    _, client, *_ = env
    assert _create(client, "root", "bp-alice").status_code == 200
