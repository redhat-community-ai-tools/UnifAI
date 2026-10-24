"""Denial uniformity of resource writes and visibility of templates."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from inbound.flask.endpoints import register_all_endpoints
from mas.resources.errors import ResourceAccessDeniedError
from mas.templates.errors import TemplateNotFoundError

USER = "regular-user"
ADMIN = "admin-user"
TPL = "/api/templates"
RES = "/api/resources"


def _h(user: str) -> dict[str, str]:
    return {"X-Authenticated-User": user}


def _template(is_public: bool):
    t = Mock()
    t.metadata.is_public = is_public
    t.model_dump.return_value = {"id": "t1"}
    return t


@pytest.fixture
def container():
    resources = Mock()
    resources.to_dict.return_value = {}
    templates = Mock()
    templates.list_template_summaries.return_value = []
    templates.count_templates.return_value = 0
    return SimpleNamespace(resources_service=resources, template_service=templates, admin_config_reader=None)


@pytest.fixture
def client(container):
    app = Flask(__name__)
    app.secret_key = "s"
    app.config["admin_allowed_users"] = [ADMIN]
    app.container = container
    register_all_endpoints(app)
    return app.test_client()


class TestResourceWriteDenial:
    def test_update_by_non_owner_looks_like_a_missing_resource(self, client, container):
        container.resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")
        denied = client.put(f"{RES}/resource.update", json={"resourceId": "r1", "config": {}}, headers=_h(USER))
        container.resources_service.guard_write_access.side_effect = KeyError("r1")
        missing = client.put(f"{RES}/resource.update", json={"resourceId": "r1", "config": {}}, headers=_h(USER))
        assert denied.status_code == missing.status_code == 404
        assert denied.get_json() == missing.get_json()
        container.resources_service.update.assert_not_called()

    def test_delete_by_non_owner_looks_like_a_missing_resource(self, client, container):
        container.resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")
        denied = client.delete(f"{RES}/resource.delete?resourceId=r1", headers=_h(USER))
        container.resources_service.guard_write_access.side_effect = KeyError("r1")
        missing = client.delete(f"{RES}/resource.delete?resourceId=r1", headers=_h(USER))
        assert denied.status_code == missing.status_code == 404
        assert denied.get_json() == missing.get_json()
        container.resources_service.delete.assert_not_called()


READ_ROUTES = [
    ("get", "templates.list"), ("get", "templates.search?q=x"), ("get", "templates.count"),
    ("get", "template.get?templateId=t1"), ("get", "template.summary.get?templateId=t1"),
    ("get", "template.schema.get?templateId=t1"),
    ("post", "template.input.validate"), ("post", "template.instantiate"),
]


class TestTemplateVisibility:
    @pytest.mark.parametrize("method,route", READ_ROUTES)
    def test_anonymous_denied(self, client, container, method, route):
        r = getattr(client, method)(f"{TPL}/{route}", **({"json": {"templateId": "t1", "input": {}}} if method == "post" else {}))
        assert r.status_code in (401, 403)
        container.template_service.get_template.assert_not_called()

    @pytest.mark.parametrize("path", ["template.get", "template.summary.get", "template.schema.get"])
    def test_private_template_is_not_found_for_a_regular_user(self, client, container, path):
        container.template_service.get_template.return_value = _template(False)
        denied = client.get(f"{TPL}/{path}?templateId=t1", headers=_h(USER))
        container.template_service.get_template.side_effect = TemplateNotFoundError("t1")
        missing = client.get(f"{TPL}/{path}?templateId=t1", headers=_h(USER))
        assert denied.status_code == missing.status_code == 404
        assert denied.get_json() == missing.get_json()

    def test_private_template_cannot_be_instantiated_by_a_regular_user(self, client, container):
        container.template_service.get_template.return_value = _template(False)
        r = client.post(f"{TPL}/template.instantiate", json={"templateId": "t1", "input": {}}, headers=_h(USER))
        assert r.status_code == 404
        container.template_service.instantiate.assert_not_called()

    def test_private_template_is_readable_by_an_admin(self, client, container):
        container.template_service.get_template.return_value = _template(False)
        r = client.get(f"{TPL}/template.get?templateId=t1", headers=_h(ADMIN))
        assert r.status_code == 200

    def test_public_template_is_readable_by_a_regular_user(self, client, container):
        container.template_service.get_template.return_value = _template(True)
        assert client.get(f"{TPL}/template.get?templateId=t1", headers=_h(USER)).status_code == 200

    def test_regular_user_cannot_list_or_count_unlisted_templates(self, client, container):
        client.get(f"{TPL}/templates.list?isPublic=false", headers=_h(USER))
        assert container.template_service.list_template_summaries.call_args.kwargs["is_public"] is True
        client.get(f"{TPL}/templates.count?isPublic=false", headers=_h(USER))
        assert container.template_service.count_templates.call_args.kwargs["is_public"] is True

    def test_admin_may_list_unlisted_templates(self, client, container):
        client.get(f"{TPL}/templates.list?isPublic=false", headers=_h(ADMIN))
        assert container.template_service.list_template_summaries.call_args.kwargs["is_public"] is False
