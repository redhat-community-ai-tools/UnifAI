"""Integration tests for the core resource endpoints in ``resources.py``.

Verifies route wiring, auth, and exception -> HTTP status-code mapping
against a mocked ``resources_service`` (see ``conftest.py``).
"""
from unittest.mock import Mock

from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceInUseError,
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
        self, client, admin_headers, resources_service, builtin_resource_service, collaboration_service,
    ):
        """Regression test: an admin bypasses ``guard_write_access``'s
        ownership check on a built-in resource (admins bypass both checks),
        but must still be rejected by the admin edit lock here just like on
        ``builtin.update`` - the lock was previously only enforced on the
        built-in-specific routes, not this generic CRUD path."""
        builtin_doc = Mock()
        builtin_resource_service.is_builtin.return_value = True
        resources_service.guard_write_access.return_value = builtin_doc

        holder = Mock(user_id="other-admin", display_name="Other Admin")
        collaboration_service.get_admin_edit_lock.return_value = holder

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 409
        resources_service.update.assert_not_called()

    def test_update_builtin_allowed_when_lock_held_by_self(
        self, client, admin_headers, resources_service, builtin_resource_service, collaboration_service,
    ):
        from tests.integration.endpoints.conftest import ADMIN_USER

        builtin_doc = Mock()
        builtin_resource_service.is_builtin.return_value = True
        resources_service.guard_write_access.return_value = builtin_doc
        resources_service.update.return_value = _fake_resource_dump()

        holder = Mock(user_id=ADMIN_USER, display_name="Admin Alice")
        collaboration_service.get_admin_edit_lock.return_value = holder

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 200

    def test_update_custom_resource_ignores_lock_check(
        self, client, admin_headers, resources_service, builtin_resource_service, collaboration_service,
    ):
        """The lock check is scoped to built-in resources only - a custom
        resource must not consult the admin edit lock at all."""
        custom_doc = Mock()
        builtin_resource_service.is_builtin.return_value = False
        resources_service.guard_write_access.return_value = custom_doc
        resources_service.update.return_value = _fake_resource_dump()

        resp = client.put(
            "/api/resources/resource.update",
            json={"resourceId": "r1", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        collaboration_service.get_admin_edit_lock.assert_not_called()


class TestDeleteResource:
    def test_delete_success(self, client, user_headers, resources_service):
        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 200
        resources_service.guard_write_access.assert_called_once()
        resources_service.delete.assert_called_once_with("r1")

    def test_delete_builtin_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service, builtin_resource_service, collaboration_service,
    ):
        """Regression test: same lock-bypass fix as resource.update, for
        the generic delete path."""
        builtin_doc = Mock()
        builtin_resource_service.is_builtin.return_value = True
        resources_service.guard_write_access.return_value = builtin_doc

        holder = Mock(user_id="other-admin", display_name="Other Admin")
        collaboration_service.get_admin_edit_lock.return_value = holder

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=admin_headers,
        )

        assert resp.status_code == 409
        resources_service.delete.assert_not_called()

    def test_delete_idor_denied_returns_403(self, client, user_headers, resources_service):
        resources_service.guard_write_access.side_effect = ResourceAccessDeniedError("r1")

        resp = client.delete(
            "/api/resources/resource.delete?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 403
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
