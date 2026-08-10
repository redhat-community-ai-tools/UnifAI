"""Flask test-client fixtures for resources/builtins endpoint integration tests.

These tests exercise the HTTP layer (route wiring, auth decorators, exception
-> status-code mapping) with a real Flask app and test client, but a mocked
``resources_service`` / ``collaboration_service`` on the container — so we
verify the endpoints' own behavior without depending on Mongo/Redis.

Authentication uses the ``X-Authenticated-User`` fallback header (see
``inbound.flask.decorators._get_fallback_user``), which lets
``require_session_identity`` resolve an identity without a real Redis-backed
session — exactly the mechanism intended for internal/service-to-service and
test callers.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from inbound.flask.endpoints import register_all_endpoints


ADMIN_USER = "admin-alice"
NON_ADMIN_USER = "bob"


def _auth_headers(username: str) -> dict[str, str]:
    return {"X-Authenticated-User": username}


_DEFAULT_RESOURCE_DICT = {"rid": "r1", "name": "thing", "category": "provider", "type": "mcp"}


@pytest.fixture
def resources_service() -> Mock:
    svc = Mock()
    # `to_dict`/`to_dicts` are the serialization boundary now that endpoints
    # no longer call `doc.model_dump()` directly (see `service.to_dict()`).
    # Default to a stable dict so `jsonify(...)` in handlers under test
    # doesn't choke on serializing a bare Mock; tests that care about the
    # exact payload shape override `.to_dict.return_value` explicitly.
    svc.to_dict.return_value = dict(_DEFAULT_RESOURCE_DICT)
    return svc


@pytest.fixture
def builtin_resource_service() -> Mock:
    svc = Mock()
    # Cascade preview defaults to "nothing to cascade" so existing
    # promote/toggle/update tests that don't care about the nested-ref
    # cascade disclaimer aren't tripped up by iterating a bare Mock.
    svc.preview_cascade_targets.return_value = []
    return svc


@pytest.fixture
def collaboration_service() -> Mock:
    return Mock()


@pytest.fixture
def admin_edit_lock_service() -> Mock:
    svc = Mock()
    # No admin edit lock held by default, so promote/update/toggle tests
    # that don't care about lock enforcement aren't spuriously rejected
    # with 409 by ``_reject_if_locked_by_other`` (a bare Mock return value
    # would otherwise be treated as a truthy, non-matching lock holder).
    svc.get_admin_edit_lock.return_value = None
    return svc


@pytest.fixture
def container(
    resources_service: Mock,
    builtin_resource_service: Mock,
    collaboration_service: Mock,
    admin_edit_lock_service: Mock,
) -> SimpleNamespace:
    return SimpleNamespace(
        resources_service=resources_service,
        builtin_resource_service=builtin_resource_service,
        collaboration_service=collaboration_service,
        admin_edit_lock_service=admin_edit_lock_service,
        admin_config_reader=None,
    )


@pytest.fixture
def app(container: SimpleNamespace) -> Flask:
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.config["admin_allowed_users"] = [ADMIN_USER]
    flask_app.container = container
    register_all_endpoints(flask_app)
    return flask_app


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    return app.test_client()


@pytest.fixture
def admin_headers() -> dict[str, str]:
    return _auth_headers(ADMIN_USER)


@pytest.fixture
def user_headers() -> dict[str, str]:
    return _auth_headers(NON_ADMIN_USER)
