"""Object-level access tests for the blueprint endpoints and service."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from flask import Flask

from inbound.flask.endpoints import register_all_endpoints
from mas.blueprints.exceptions import (
    BlueprintAccessDeniedError,
    BlueprintNotFoundError,
    InvalidMetadataKeysError,
)
from mas.blueprints.models.blueprint import BlueprintDocument
from mas.blueprints.service import BlueprintService
from mas.core.identity import Identity

OWNER = "owner-user"
OTHER = "other-user"
BASE = "/api/blueprints"


def _doc(owner: Identity, scope: str | None = None, bp_id: str = "bp-1") -> BlueprintDocument:
    return BlueprintDocument(
        blueprint_id=bp_id,
        identity=owner,
        spec_dict={
            "name": "Flow",
            "plan": [{"secret": "system prompt"}],
            "prompt_shortcuts": [{"id": "a1b2c3d4", "text": "hi"}] * 5,
        },
        metadata={"usageScope": scope} if scope else {"internal": "x"},
    )


@pytest.fixture
def repo() -> Mock:
    r = Mock()
    r.set_metadata.return_value = True
    r.delete.return_value = True
    r.exists.return_value = True
    return r


@pytest.fixture
def service(repo) -> BlueprintService:
    svc = BlueprintService(repo=repo, resolver=Mock())
    svc.validate_blueprint = Mock(return_value=SimpleNamespace(model_dump=lambda: {"ok": True}))
    return svc


@pytest.fixture
def client(service):
    app = Flask(__name__)
    app.secret_key = "s"
    app.config["admin_allowed_users"] = []
    app.container = SimpleNamespace(blueprint_service=service, admin_config_reader=None)
    register_all_endpoints(app)
    return app.test_client()


def _h(user: str) -> dict[str, str]:
    return {"X-Authenticated-User": user}


def _load(repo, doc):
    def _l(bid):
        if bid != doc.blueprint_id:
            raise KeyError(bid)
        return doc
    repo.load.side_effect = _l


class TestInfoGet:
    def test_anonymous_denied(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "public"))
        assert client.get(f"{BASE}/blueprint.info.get?blueprintId=bp-1").status_code in (401, 403)

    def test_owner_gets_full_document(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        r = client.get(f"{BASE}/blueprint.info.get?blueprintId=bp-1", headers=_h(OWNER))
        assert r.status_code == 200
        assert "plan" in r.get_json()["spec_dict"]

    def test_other_user_gets_uniform_404_for_private(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "private"))
        denied = client.get(f"{BASE}/blueprint.info.get?blueprintId=bp-1", headers=_h(OTHER))
        missing = client.get(f"{BASE}/blueprint.info.get?blueprintId=nope", headers=_h(OTHER))
        assert denied.status_code == missing.status_code == 404
        assert denied.get_json() == missing.get_json()

    def test_public_blueprint_returns_minimal_fields(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "public"))
        r = client.get(f"{BASE}/blueprint.info.get?blueprintId=bp-1", headers=_h(OTHER))
        body = r.get_json()
        assert r.status_code == 200
        assert set(body["spec_dict"]) == {"name", "prompt_shortcuts"}
        assert len(body["spec_dict"]["prompt_shortcuts"]) <= 3
        assert body["metadata"] == {"usageScope": "public"}
        assert body["user_id"] == OWNER


class TestRemove:
    def test_anonymous_denied(self, client, repo):
        r = client.delete(f"{BASE}/remove.blueprint?blueprintId=bp-1")
        assert r.status_code in (401, 403)
        repo.delete.assert_not_called()

    def test_owner_deletes(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        assert client.delete(f"{BASE}/remove.blueprint?blueprintId=bp-1", headers=_h(OWNER)).status_code == 200
        repo.delete.assert_called_once_with("bp-1")

    def test_other_denied_even_if_public(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "public"))
        r = client.delete(f"{BASE}/remove.blueprint?blueprintId=bp-1", headers=_h(OTHER))
        assert r.status_code == 404
        repo.delete.assert_not_called()


class TestMetadataSet:
    def _put(self, client, user, metadata):
        return client.put(
            f"{BASE}/blueprint.metadata.set",
            json={"blueprintId": "bp-1", "metadata": metadata},
            headers=_h(user) if user else {},
        )

    def test_anonymous_denied(self, client, repo):
        assert self._put(client, None, {"usageScope": "public"}).status_code in (401, 403)
        repo.set_metadata.assert_not_called()

    def test_owner_sets_usage_scope(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        assert self._put(client, OWNER, {"usageScope": "public"}).status_code == 200
        repo.set_metadata.assert_called_once()

    def test_other_denied_uniform(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        assert self._put(client, OTHER, {"usageScope": "public"}).status_code == 404
        repo.set_metadata.assert_not_called()

    def test_unknown_key_rejected(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        assert self._put(client, OWNER, {"owner": "x"}).status_code == 400
        repo.set_metadata.assert_not_called()

    def test_bad_scope_value_rejected(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER)))
        assert self._put(client, OWNER, {"usageScope": "everyone"}).status_code == 400


class TestOtherRoutes:
    def test_resolved_by_id_other_denied(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "public"))
        r = client.get(f"{BASE}/available.blueprints.resolved.get?blueprintId=bp-1", headers=_h(OTHER))
        assert r.status_code == 404

    def test_validate_anonymous_denied(self, client):
        assert client.post(f"{BASE}/blueprint.validate", json={"blueprintId": "bp-1"}).status_code in (401, 403)

    def test_validate_private_other_denied(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "private"))
        r = client.post(f"{BASE}/blueprint.validate", json={"blueprintId": "bp-1"}, headers=_h(OTHER))
        assert r.status_code == 404

    def test_validate_public_other_allowed(self, client, repo):
        _load(repo, _doc(Identity.user(OWNER), "public"))
        r = client.post(f"{BASE}/blueprint.validate", json={"blueprintId": "bp-1"}, headers=_h(OTHER))
        assert r.status_code == 200

    def test_draft_validate_anonymous_denied(self, client):
        assert client.post(f"{BASE}/draft.validate", json={"draft": "{}"}).status_code in (401, 403)

    def test_schema_anonymous_denied(self, client):
        assert client.get(f"{BASE}/blueprint.draft.schema.get").status_code in (401, 403)

    def test_schema_authenticated_ok(self, client):
        assert client.get(f"{BASE}/blueprint.draft.schema.get", headers=_h(OTHER)).status_code == 200


class TestServiceTeamAccess:
    def test_team_owner_identity_matches(self, service, repo):
        _load(repo, _doc(Identity.team("t1")))
        assert service.get_accessible_doc("bp-1", Identity.team("t1")).blueprint_id == "bp-1"

    def test_user_with_same_id_as_team_denied(self, service, repo):
        _load(repo, _doc(Identity.team("t1")))
        with pytest.raises(BlueprintAccessDeniedError):
            service.get_accessible_doc("bp-1", Identity.user("t1"))

    def test_missing_raises_not_found(self, service, repo):
        repo.load.side_effect = KeyError("x")
        with pytest.raises(BlueprintNotFoundError):
            service.get_accessible_doc("x", Identity.user(OWNER))

    def test_client_metadata_whitelist(self, service):
        with pytest.raises(InvalidMetadataKeysError):
            service.set_metadata_owned("bp-1", {"foo": 1}, Identity.user(OWNER))
