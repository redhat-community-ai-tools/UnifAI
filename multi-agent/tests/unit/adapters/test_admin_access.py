"""Unit tests for admin gating in ``inbound.flask.decorators``.

Covers both branches of ``is_admin_user`` — the container-based
``admin_config_reader`` and the static ``admin_allowed_users`` Flask-config
fallback — plus ``require_admin_access``'s exception handling, none of which
were previously exercised (existing integration fixtures always set
``admin_config_reader=None``, so only the fallback path ran).
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from inbound.flask.decorators import is_admin_user, require_admin_access


ADMIN_USER = "Admin-Alice"
OTHER_USER = "bob"


def _make_app(*, admin_config_reader=None, admin_allowed_users=None) -> Flask:
    app = Flask(__name__)
    app.config["admin_allowed_users"] = admin_allowed_users or []
    app.container = SimpleNamespace(admin_config_reader=admin_config_reader)
    return app


class TestIsAdminUser:
    def test_reader_true_grants_admin_even_if_not_in_allowed_users(self):
        reader = Mock()
        reader.is_admin.return_value = True
        app = _make_app(admin_config_reader=reader, admin_allowed_users=[])

        with app.test_request_context():
            assert is_admin_user(OTHER_USER) is True
        reader.is_admin.assert_called_once_with(OTHER_USER)

    def test_reader_false_falls_back_to_allowed_users(self):
        reader = Mock()
        reader.is_admin.return_value = False
        app = _make_app(admin_config_reader=reader, admin_allowed_users=[ADMIN_USER])

        with app.test_request_context():
            assert is_admin_user(ADMIN_USER) is True
            assert is_admin_user(OTHER_USER) is False

    def test_allowed_users_match_is_case_insensitive(self):
        app = _make_app(admin_config_reader=None, admin_allowed_users=[ADMIN_USER])

        with app.test_request_context():
            assert is_admin_user(ADMIN_USER.lower()) is True
            assert is_admin_user(ADMIN_USER.upper()) is True


class TestRequireAdminAccess:
    def _build_client(self, *, admin_config_reader=None, admin_allowed_users=None):
        app = _make_app(
            admin_config_reader=admin_config_reader,
            admin_allowed_users=admin_allowed_users,
        )

        @app.route("/admin-only")
        @require_admin_access
        def admin_only():
            from flask import jsonify
            return jsonify({"ok": True})

        return app.test_client()

    def test_returns_500_and_logs_when_reader_raises(self, caplog):
        reader = Mock()
        reader.is_admin.side_effect = RuntimeError("mongo down")
        client = self._build_client(admin_config_reader=reader, admin_allowed_users=[ADMIN_USER])

        with caplog.at_level("ERROR"):
            resp = client.get("/admin-only", headers={"X-Authenticated-User": ADMIN_USER})

        assert resp.status_code == 500
        assert resp.get_json()["error_type"] == "ACCESS_CONTROL_ERROR"
        assert "Admin access check failed unexpectedly" in caplog.text

    def test_grants_access_when_reader_confirms_admin(self):
        reader = Mock()
        reader.is_admin.return_value = True
        client = self._build_client(admin_config_reader=reader, admin_allowed_users=[])

        resp = client.get("/admin-only", headers={"X-Authenticated-User": OTHER_USER})

        assert resp.status_code == 200

    def test_denies_access_when_neither_reader_nor_allowed_users_match(self):
        reader = Mock()
        reader.is_admin.return_value = False
        client = self._build_client(admin_config_reader=reader, admin_allowed_users=[ADMIN_USER])

        resp = client.get("/admin-only", headers={"X-Authenticated-User": OTHER_USER})

        assert resp.status_code == 403
        assert resp.get_json()["error_type"] == "ACCESS_DENIED"
