"""Caller binding of the validation endpoints (graph, resource, config, blueprint).

Every route must need a session, resolve referenced objects with the caller's
scope (never the anonymous default), and take the credential lookup identity
from the verified session instead of the request body.
"""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from inbound.flask.endpoints import register_all_endpoints

USER = "caller-user"
GRAPH = "/api/graph/validation"
RES = "/api/resources"
BP = "/api/blueprints"

GRAPH_POST_ROUTES = [
    "channels.validate", "all.validate", "dependencies.validate",
    "cycles.validate", "orphans.validate", "required_nodes.validate",
]
DRAFT_YAML = "name: x\nplan: []\n"


def _h(user: str = USER) -> dict[str, str]:
    return {"X-Authenticated-User": user}


@pytest.fixture
def container():
    result = SimpleNamespace(model_dump=lambda *a, **k: {"ok": True})
    blueprint_service = Mock()
    blueprint_service.resolve_draft_dict.side_effect = RuntimeError("stop after resolve")
    blueprint_service.validate_blueprint.return_value = result
    resources_service = Mock()
    resources_service.validate_config.return_value = result
    resources_service.validate_resource.return_value = result
    return SimpleNamespace(
        blueprint_service=blueprint_service,
        resources_service=resources_service,
        graph_validation_service=Mock(),
        graph_service=Mock(),
        admin_config_reader=None,
    )


@pytest.fixture
def client(container):
    app = Flask(__name__)
    app.secret_key = "s"
    app.config["admin_allowed_users"] = []
    app.container = container
    register_all_endpoints(app)
    return app.test_client()


class TestGraphValidation:
    @pytest.mark.parametrize("route", GRAPH_POST_ROUTES)
    def test_anonymous_denied_and_nothing_resolved(self, client, container, route):
        r = client.post(f"{GRAPH}/{route}", data=DRAFT_YAML)
        assert r.status_code in (401, 403)
        container.blueprint_service.resolve_draft_dict.assert_not_called()

    def test_names_anonymous_denied(self, client):
        assert client.get(f"{GRAPH}/names.get").status_code in (401, 403)

    @pytest.mark.parametrize("route", GRAPH_POST_ROUTES)
    def test_draft_resolved_with_the_callers_scope(self, client, container, route):
        r = client.post(f"{GRAPH}/{route}", data=DRAFT_YAML, headers=_h())
        container.blueprint_service.resolve_draft_dict.assert_called_once()
        caller = container.blueprint_service.resolve_draft_dict.call_args.kwargs["caller"]
        assert caller.identity is not None and caller.identity.id == USER
        assert "traceback" not in r.get_json()


class TestConfigValidate:
    BODY = {"category": "tool", "type": "x", "config": {}}

    def test_anonymous_denied(self, client, container):
        r = client.post(f"{RES}/config.validate", json=self.BODY)
        assert r.status_code in (401, 403)
        container.resources_service.validate_config.assert_not_called()

    def test_validated_with_the_callers_scope(self, client, container):
        r = client.post(f"{RES}/config.validate", json=self.BODY, headers=_h())
        assert r.status_code == 200
        caller = container.resources_service.validate_config.call_args.kwargs["caller"]
        assert caller.identity.id == USER

    def test_foreign_reference_is_a_plain_not_found(self, client, container):
        container.resources_service.validate_config.side_effect = KeyError("rid-of-someone-else")
        r = client.post(f"{RES}/config.validate", json=self.BODY, headers=_h())
        assert r.status_code == 404


class TestCredentialLookupIdentity:
    def test_resource_validate_ignores_body_user_id(self, client, container):
        r = client.post(
            f"{RES}/resource.validate",
            json={"resourceId": "r1", "userId": "victim"}, headers=_h(),
        )
        assert r.status_code == 200
        assert container.resources_service.validate_resource.call_args.kwargs["user_id"] == USER

    def test_resources_validate_ignores_body_user_id(self, client, container):
        container.resources_service.validate_resources.return_value = {}
        client.post(
            f"{RES}/resources.validate",
            json={"resourceIds": ["r1"], "userId": "victim"}, headers=_h(),
        )
        assert container.resources_service.validate_resources.call_args.kwargs["user_id"] == USER

    def test_blueprint_validate_ignores_body_user_id(self, client, container):
        client.post(
            f"{BP}/blueprint.validate",
            json={"blueprintId": "b1", "userId": "victim"}, headers=_h(),
        )
        assert container.blueprint_service.validate_blueprint.call_args.kwargs["user_id"] == USER
