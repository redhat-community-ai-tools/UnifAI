"""Tests for RequestRules correlation middleware."""
from __future__ import annotations

from flask import Flask, jsonify

from global_utils.flask.correlation import REQUEST_ID_HEADER
from global_utils.flask.request_rules import RequestRules
from global_utils.utils.logging_config import get_request_id, get_session_id


def _make_app():
    app = Flask(__name__)
    RequestRules(app)

    @app.get("/ping")
    def ping():
        return jsonify({
            "request_id": get_request_id(),
            "session_id": get_session_id(),
        })

    return app


def test_generates_request_id_when_missing():
    client = _make_app().test_client()
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.headers.get(REQUEST_ID_HEADER, "").startswith("req-")
    assert resp.get_json()["request_id"].startswith("req-")


def test_echoes_incoming_request_id():
    client = _make_app().test_client()
    resp = client.get("/ping", headers={REQUEST_ID_HEADER: "req-fixed-1"})
    assert resp.headers.get(REQUEST_ID_HEADER) == "req-fixed-1"
    assert resp.get_json()["request_id"] == "req-fixed-1"


def test_binds_session_id_from_query():
    client = _make_app().test_client()
    resp = client.get("/ping?sessionId=sess-xyz")
    assert resp.get_json()["session_id"] == "sess-xyz"
