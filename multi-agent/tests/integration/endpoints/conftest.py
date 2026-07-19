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

from inbound.flask.endpoints import register_all_endpoints


ADMIN_USER = "admin-alice"
NON_ADMIN_USER = "bob"


def _auth_headers(username: str) -> dict:
    return {"X-Authenticated-User": username}


@pytest.fixture
def resources_service():
    return Mock()


@pytest.fixture
def collaboration_service():
    return Mock()


@pytest.fixture
def container(resources_service, collaboration_service):
    return SimpleNamespace(
        resources_service=resources_service,
        collaboration_service=collaboration_service,
        admin_config_reader=None,
    )


@pytest.fixture
def app(container):
    flask_app = Flask(__name__)
    flask_app.secret_key = "test-secret"
    flask_app.config["admin_allowed_users"] = [ADMIN_USER]
    flask_app.container = container
    register_all_endpoints(flask_app)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def admin_headers():
    return _auth_headers(ADMIN_USER)


@pytest.fixture
def user_headers():
    return _auth_headers(NON_ADMIN_USER)
