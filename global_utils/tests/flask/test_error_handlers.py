"""Tests for app-level error handlers."""
from __future__ import annotations

from flask import Flask

from global_utils.flask.correlation import REQUEST_ID_HEADER, bind_request_id_from_headers
from global_utils.flask.error_handlers import register_error_handlers
from global_utils.flask.request_rules import RequestRules


def _make_app():
    app = Flask(__name__)
    RequestRules(app)
    register_error_handlers(app)

    @app.get("/boom")
    def boom():
        raise RuntimeError("kaboom")

    @app.get("/missing")
    def missing():
        from werkzeug.exceptions import NotFound
        raise NotFound(description="nope")

    return app


def test_uncaught_exception_shape():
    client = _make_app().test_client()
    resp = client.get("/boom", headers={REQUEST_ID_HEADER: "req-err-1"})
    assert resp.status_code == 500
    body = resp.get_json()
    assert body["error_type"] == "INTERNAL_ERROR"
    assert body["request_id"] == "req-err-1"
    assert "error" in body


def test_http_exception_shape():
    client = _make_app().test_client()
    resp = client.get("/missing", headers={REQUEST_ID_HEADER: "req-404"})
    assert resp.status_code == 404
    body = resp.get_json()
    assert body["request_id"] == "req-404"
    assert body["error_type"]
