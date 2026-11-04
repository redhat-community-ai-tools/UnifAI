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

    def test_update_idor_denied_returns_403(self, client, user_headers, resources_service):
        """Regression test: a caller updating someone else's custom resource
        must get 403 from the guard, not proceed to update()."""
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=user_headers,
        )

        assert resp.status_code == 403
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

    def test_delete_idor_denied_returns_403(self, client, user_headers, resources_service):
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 403
        resources_service.delete.assert_not_called()

    def test_delete_in_use_returns_409_with_usage(
        self, client, user_headers, resources_service, deletion_service,
    ):
        resources_service.delete.side_effect = ResourceInUseError(
            by_blueprints=["bp1"], by_resources=[],
        )
        payload = Mock()
        payload.model_dump.return_value = {
            "in_use": True,
            "category": "nodes",
            "allowed_mode": "cascade",
            "blueprints": [{"id": "bp1", "name": "Workflow"}],
            "resources": [],
        }
        deletion_service.usage_payload_for_in_use.return_value = payload

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 409
        body = resp.get_json()
        assert body["code"] == "RESOURCE_IN_USE"
        assert body["blueprints"] == [{"id": "bp1", "name": "Workflow"}]
        deletion_service.usage_payload_for_in_use.assert_called_once()


class TestForceDeleteResource:
    """Verifies /resource.force-delete and /resource.check-usage stay behind write access."""

    def test_check_usage_checks_write_access(
        self, client, user_headers, resources_service, deletion_service,
    ):
        payload = Mock()
        payload.model_dump.return_value = {"in_use": False}
        deletion_service.check_usage.return_value = payload

        resp = client.get(
            "/api/resources/resource.check-usage?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["in_use"] is False
        resources_service.guard_write_access.assert_called_once()
        deletion_service.check_usage.assert_called_once_with("r1")

    def test_check_usage_denied_returns_403(
        self, client, user_headers, resources_service, deletion_service,
    ):
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.get(
            "/api/resources/resource.check-usage?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 403
        deletion_service.check_usage.assert_not_called()

    def test_check_usage_unexpected_error_hides_details(
        self, client, user_headers, deletion_service,
    ):
        deletion_service.check_usage.side_effect = RuntimeError("mongo uri secret")

        resp = client.get(
            "/api/resources/resource.check-usage?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Internal server error"
        assert "secret" not in resp.get_data(as_text=True)

    def test_force_delete_passes_caller(
        self, client, user_headers, deletion_service,
    ):
        resp = client.post(
            "/api/resources/resource.force-delete",
            json={"resourceId": "r1", "mode": "detach"},
            headers=user_headers,
        )

        assert resp.status_code == 200
        deletion_service.force_delete.assert_called_once()
        args, kwargs = deletion_service.force_delete.call_args
        assert args[0] == "r1"
        assert args[1] == "detach"
        assert kwargs["caller"].identity.id == "bob"
        assert kwargs["username"] == "bob"

    def test_force_delete_denied_returns_403(
        self, client, user_headers, deletion_service,
    ):
        deletion_service.force_delete.side_effect = ResourceAccessDeniedError("r1")

        resp = client.post(
            "/api/resources/resource.force-delete",
            json={"resourceId": "r1", "mode": "detach"},
            headers=user_headers,
        )

        assert resp.status_code == 403


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
