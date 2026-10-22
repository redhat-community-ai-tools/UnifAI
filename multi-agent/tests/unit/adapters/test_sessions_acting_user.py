"""Team workspaces: the acting user of a run is the signed-in person, not the team."""
from types import SimpleNamespace

from flask import Flask, g

from inbound.flask.decorators import acting_user


def _ctx(username):
    app = Flask(__name__)
    ctx = app.test_request_context()
    ctx.push()
    if username is not None:
        g.identity_username = username
    return ctx


def test_team_workspace_uses_the_signed_in_username():
    ctx = _ctx("alice")
    try:
        assert acting_user(SimpleNamespace(id="team-123")) == "alice"
    finally:
        ctx.pop()


def test_personal_workspace_is_unchanged():
    ctx = _ctx("alice")
    try:
        assert acting_user(SimpleNamespace(id="alice")) == "alice"
    finally:
        ctx.pop()


def test_falls_back_to_the_identity_without_a_session_username():
    ctx = _ctx(None)
    try:
        assert acting_user(SimpleNamespace(id="svc-account")) == "svc-account"
    finally:
        ctx.pop()
