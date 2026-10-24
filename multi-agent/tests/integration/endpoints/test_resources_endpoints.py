"""Integration tests for the core resource endpoints in ``resources.py``.

Verifies route wiring, auth, and exception -> HTTP status-code mapping
against a mocked ``resources_service`` (see ``conftest.py``).
"""
from unittest.mock import Mock

from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceInUseError,
    ResourceLockedError,
)


def _fake_resource_dump() -> Mock:
    """A stand-in for a ``Resource`` returned by the service. Endpoints now
    serialize via ``resources_service.to_dict(doc)`` rather than
    ``doc.model_dump()`` — see the ``resources_service`` fixture, which
    stubs ``to_dict`` with a stable default dict (overridden per-test via
    ``resources_service.to_dict.return_value = {...}`` when a test cares
    about the exact payload)."""
    return Mock()


class TestSaveResource:
    """Verifies /resource.save creates a resource and returns 201."""

    def test_save_success_returns_201(self, client, user_headers, resources_service):
        resources_service.create.return_value = _fake_resource_dump()

        resp = client.post(
            "/api/resources/resource.save",
            json={"category": "provider", "type": "mcp", "name": "thing", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 201
        assert resp.get_json()["rid"] == "r1"

    def test_save_value_error_returns_400(self, client, user_headers, resources_service):
        resources_service.create.side_effect = ValueError("bad schema")

        resp = client.post(
            "/api/resources/resource.save",
            json={"category": "provider", "type": "mcp", "name": "thing", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 400
        assert "bad schema" in resp.get_json()["error"]


class TestGetResource:
    """Verifies /resource.get retrieves a resource with visibility enforcement."""

    def test_get_success(self, client, user_headers, resources_service):
        resources_service.get_visible.return_value = _fake_resource_dump()

        resp = client.get(
            "/api/resources/resource.get?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 200
        resources_service.get_visible.assert_called_once()

    def test_get_not_found_returns_404(self, client, user_headers, resources_service):
        resources_service.get_visible.side_effect = KeyError("r1")

        resp = client.get(
            "/api/resources/resource.get?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 404


class TestUpdateResource:
    """Verifies /resource.update enforces write-access guards and lock checks."""

    def test_update_success(self, client, user_headers, resources_service):
        resources_service.update.return_value = _fake_resource_dump()

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 200
        resources_service.guard_write_access.assert_called_once()

    def test_update_builtin_write_protected_returns_403(self, client, user_headers, resources_service):
        resources_service.guard_write_access.side_effect = BuiltInWriteProtectedError()

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 403
        resources_service.update.assert_not_called()

    def test_update_idor_denied_looks_like_not_found(self, client, user_headers, resources_service):
        """Regression test: a caller updating someone else's custom resource
        must get the same 404 as for a missing one, not proceed to update()."""
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 404
        resources_service.update.assert_not_called()

    def test_update_not_found_returns_404(self, client, user_headers, resources_service):
        resources_service.guard_write_access.side_effect = KeyError("r1")

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 404

    def test_update_builtin_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service,
    ):
        """Regression test: ``guard_write_access`` now enforces the admin
        edit lock internally for built-in resources, raising
        ``ResourceLockedError`` when another admin holds the lock."""
        resources_service.guard_write_access.side_effect = ResourceLockedError(
            locked_by_user_id="other-admin", locked_by_display_name="Other Admin",
        )

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 409
        body = resp.get_json()
        assert body["lockedBy"]["userId"] == "other-admin"
        resources_service.update.assert_not_called()

    def test_update_succeeds_when_lock_held_by_self(
        self, client, admin_headers, resources_service,
    ):
        """No lock error means the lock is held by the caller (or no lock
        exists) — ``guard_write_access`` returns normally."""
        resources_service.guard_write_access.return_value = _fake_resource_dump()
        resources_service.update.return_value = _fake_resource_dump()

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 200


class TestDeleteResource:
    """Verifies /resource.delete enforces write-access, in-use, and lock guards."""

    def test_delete_success(self, client, user_headers, resources_service):
        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 200
        resources_service.guard_write_access.assert_called_once()
        resources_service.delete.assert_called_once_with("r1")

    def test_delete_builtin_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service,
    ):
        """Regression test: ``guard_write_access`` enforces the admin edit
        lock for built-in resources, raising ``ResourceLockedError``."""
        resources_service.guard_write_access.side_effect = ResourceLockedError(
            locked_by_user_id="other-admin", locked_by_display_name="Other Admin",
        )

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=admin_headers,
        )

        assert resp.status_code == 409
        body = resp.get_json()
        assert body["lockedBy"]["userId"] == "other-admin"
        resources_service.delete.assert_not_called()

    def test_delete_idor_denied_looks_like_not_found(self, client, user_headers, resources_service):
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 404
        resources_service.delete.assert_not_called()

    def test_delete_in_use_returns_400_with_usage(self, client, user_headers, resources_service):
        resources_service.delete.side_effect = ResourceInUseError(
            by_blueprints=["bp1"], by_resources=[],
        )

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert body["blueprints"] == ["bp1"]


class TestValidateResource:
    """Verifies /resource.validate resolves dependencies and returns validation results."""

    def test_validate_not_found_returns_404(self, client, user_headers, resources_service):
        resources_service.validate_resource.side_effect = KeyError("r1")

        resp = client.post(
            "/api/resources/resource.validate",
            json={"resourceId": "r1"},
            headers=user_headers,
        )

        assert resp.status_code == 404

    def test_validate_success(self, client, user_headers, resources_service):
        result = Mock()
        result.model_dump.return_value = {"is_valid": True}
        resources_service.validate_resource.return_value = result

        resp = client.post(
            "/api/resources/resource.validate",
            json={"resourceId": "r1"},
            headers=user_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["is_valid"] is True


class TestResourceCards:
    """Verifies /resources.cards builds element cards with identity-scoped overlays."""

    def test_empty_resource_ids_short_circuits(self, client, user_headers, resources_service):
        resp = client.post(
            "/api/resources/resources.cards",
            json={"resourceIds": []},
            headers=user_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json() == {}
        resources_service.get_cards.assert_not_called()

    def test_cards_pass_identity_and_admin_flag(self, client, user_headers, resources_service):
        card = Mock()
        card.model_dump.return_value = {"rid": "r1"}
        resources_service.get_cards.return_value = {"r1": card}

        resp = client.post(
            "/api/resources/resources.cards",
            json={"resourceIds": ["r1"]},
            headers=user_headers,
        )

        assert resp.status_code == 200
        _, kwargs = resources_service.get_cards.call_args
        assert kwargs["rids"] == ["r1"]
        assert kwargs["caller"].is_admin is False


FORBIDDEN_BODY = {"error": "Forbidden", "error_type": "ACCESS_CONTROL_ERROR"}


class TestUniformForbiddenBody:
    """Write denials answer exactly like a missing resource (no existence oracle)."""

    def test_update_and_delete_denied_use_uniform_body(
        self, client, user_headers, resources_service,
    ):
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("secret-rid")

        upd = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "secret-rid", "config": {}},
            headers=user_headers,
        )
        dele = client.delete(
            "/api/resources/resource.delete?resourceId=secret-rid",
            headers=user_headers,
        )

        resources_service.guard_write_access.side_effect = KeyError("secret-rid")
        upd_missing = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "secret-rid", "config": {}},
            headers=user_headers,
        )
        dele_missing = client.delete(
            "/api/resources/resource.delete?resourceId=secret-rid",
            headers=user_headers,
        )

        for denied, missing in ((upd, upd_missing), (dele, dele_missing)):
            assert denied.status_code == missing.status_code == 404
            assert denied.get_json() == missing.get_json()
        resources_service.update.assert_not_called()
        resources_service.delete.assert_not_called()

    def test_validate_denied_returns_403_not_500(
        self, client, user_headers, resources_service,
    ):
        # ResourceAccessDeniedError is a RuntimeError subclass: it must not be
        # swallowed by the generic RuntimeError -> 500 branch.
        resources_service.validate_resource.side_effect = ResourceAccessDeniedError("r1")

        resp = client.post(
            "/api/resources/resource.validate",
            json={"resourceId": "r1"},
            headers=user_headers,
        )

        assert resp.status_code == 403
        assert resp.get_json() == FORBIDDEN_BODY

    def test_denial_escaping_an_endpoint_is_mapped_by_the_decorator(
        self, app, client, user_headers,
    ):
        """Defense in depth: an access-denied error that a route forgot to
        catch must surface as 403, never as the decorator's 500."""
        from inbound.flask.decorators import with_require_identity_authorization
        from mas.blueprints.exceptions import BlueprintAccessDeniedError

        @app.route("/probe/resource")
        @with_require_identity_authorization
        def _probe_resource(identity):
            raise ResourceAccessDeniedError("secret-rid")

        @app.route("/probe/blueprint")
        @with_require_identity_authorization
        def _probe_blueprint(identity):
            raise BlueprintAccessDeniedError("secret-bp", "bob")

        for path in ("/probe/resource", "/probe/blueprint"):
            resp = client.get(path, headers=user_headers)
            assert resp.status_code == 403
            assert resp.get_json() == FORBIDDEN_BODY

    def test_request_validation_error_is_not_a_500(
        self, client, user_headers,
    ):
        resp = client.delete("/api/resources/resource.delete", headers=user_headers)

        assert resp.status_code == 422

    def test_owner_and_admin_still_succeed(
        self, client, user_headers, admin_headers, resources_service,
    ):
        for headers in (user_headers, admin_headers):
            resp = client.delete(
                "/api/resources/resource.delete?resourceId=r1", headers=headers,
            )
            assert resp.status_code == 200
