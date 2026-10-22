"""Access control on workspace.cleanup."""
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


def _cleanup(client, user, kind, ident):
    return client.delete("/workspace.cleanup", headers=_h(user),
                         json={"identityType": kind, "identityId": ident})


def test_cleanup_own_workspace(env):
    _, client, *_ = env
    assert _cleanup(client, "alice", "user", "alice").status_code == 200


def test_cleanup_other_users_workspace_denied(env):
    app, client, *_ = env
    assert _cleanup(client, "mallory", "user", "alice").status_code == 403
    app.container.resource_repo.delete_by_identity.assert_not_called()


def test_cleanup_team_requires_membership(env):
    _, client, *_ = env
    assert _cleanup(client, "carol", "team", "team-1").status_code == 200
    assert _cleanup(client, "mallory", "team", "team-1").status_code == 403


def test_cleanup_admin_any(env):
    _, client, *_ = env
    assert _cleanup(client, "root", "user", "alice").status_code == 200


def test_cleanup_requires_authentication(env):
    _, client, *_ = env
    resp = client.delete("/workspace.cleanup",
                         json={"identityType": "user", "identityId": "alice"})
    assert resp.status_code in (401, 403)
