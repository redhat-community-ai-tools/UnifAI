"""Integration tests for the built-in resource endpoints in ``builtins.py``.

Covers admin gating, exception -> HTTP status-code mapping (including the
domain errors that route through ``BuiltinConfigUnavailableError`` /
``BuiltInWriteProtectedError`` / ``ResourceAccessDeniedError``), and that
admin edit-lock routes degrade gracefully when collaboration isn't
configured.
"""
from unittest.mock import Mock

from mas.resources.errors import (
    BuiltInWriteProtectedError,
    BuiltinConfigUnavailableError,
    BuiltinDependentsPublicError,
)


def _fake_resource_dump(**overrides):
    base = {"rid": "r1", "name": "thing", "category": "provider", "type": "mcp"}
    base.update(overrides)
    doc = Mock()
    doc.model_dump.return_value = base
    return doc


def _fake_dependency(rid="dep-1", name="Dependency", category="llms"):
    """A stand-in for a ``Resource`` returned by ``preview_cascade_targets`` /
    ``BuiltinDependentsPublicError.dependents`` — the endpoint reads plain
    ``.rid`` / ``.name`` / ``.category`` attributes off these (not
    ``model_dump()``), so set them directly rather than via the Mock
    constructor (``name=`` there configures the mock's repr, not an attribute).
    """
    dep = Mock()
    dep.rid = rid
    dep.name = name
    dep.category = category
    return dep


class TestAdminGating:
    """/builtins.list and other admin-only routes must reject non-admins."""

    def test_non_admin_gets_403(self, client, user_headers, resources_service):
        resp = client.get("/api/resources/builtins.list", headers=user_headers)
        assert resp.status_code == 403
        resources_service.find_all_builtins.assert_not_called()

    def test_admin_gets_200(self, client, admin_headers, resources_service):
        resources_service.find_all_builtins.return_value = [_fake_resource_dump()]

        resp = client.get("/api/resources/builtins.list", headers=admin_headers)

        assert resp.status_code == 200
        assert resp.get_json()["resources"] == [{"rid": "r1", "name": "thing", "category": "provider", "type": "mcp"}]

    def test_no_auth_header_gets_401(self, client, resources_service):
        resp = client.get("/api/resources/builtins.list")
        assert resp.status_code == 401


class TestGetBuiltinSchema:
    def test_success(self, client, user_headers, resources_service):
        resources_service.get_builtin_schema.return_value = {"properties": {}}

        resp = client.get(
            "/api/resources/builtin.schema?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 200

    def test_draft_builtin_not_visible_returns_404(self, client, user_headers, resources_service):
        resources_service.get_builtin_schema.side_effect = KeyError("r1")

        resp = client.get(
            "/api/resources/builtin.schema?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 404

    def test_not_a_builtin_returns_400(self, client, user_headers, resources_service):
        resources_service.get_builtin_schema.side_effect = ValueError("not a built-in")

        resp = client.get(
            "/api/resources/builtin.schema?resourceId=r1",
            headers=user_headers,
        )

        assert resp.status_code == 400


class TestConfigureBuiltin:
    def test_success(self, client, user_headers, resources_service):
        resources_service.configure_builtin.return_value = _fake_resource_dump()

        resp = client.patch(
            "/api/resources/builtin.configure",
            json={"resourceId": "r1", "config": {"bearer_token": "secret"}},
            headers=user_headers,
        )

        assert resp.status_code == 200

    def test_unavailable_repo_returns_503(self, client, user_headers, resources_service):
        """Regression test: configure_builtin without a configured overlay
        repo must surface as 503, not a generic 500 or AttributeError."""
        resources_service.configure_builtin.side_effect = BuiltinConfigUnavailableError()

        resp = client.patch(
            "/api/resources/builtin.configure",
            json={"resourceId": "r1", "config": {"bearer_token": "secret"}},
            headers=user_headers,
        )

        assert resp.status_code == 503

    def test_draft_builtin_returns_404(self, client, user_headers, resources_service):
        resources_service.configure_builtin.side_effect = KeyError("r1")

        resp = client.patch(
            "/api/resources/builtin.configure",
            json={"resourceId": "r1", "config": {"bearer_token": "secret"}},
            headers=user_headers,
        )

        assert resp.status_code == 404


class TestDuplicateResource:
    def test_success_returns_201(self, client, user_headers, resources_service):
        resources_service.duplicate_builtin.return_value = _fake_resource_dump(rid="clone-1")

        resp = client.post(
            "/api/resources/resource.duplicate",
            json={"resourceId": "r1", "name": "my-clone"},
            headers=user_headers,
        )

        assert resp.status_code == 201
        assert resp.get_json()["rid"] == "clone-1"


class TestCascadePreview:
    """Read-only preview so the UI can confirm *before* promoting/toggling,
    instead of only disclaiming the cascade after the mutation happened."""

    def test_requires_admin(self, client, user_headers, resources_service):
        resp = client.get(
            "/api/resources/builtin.cascade-preview?resourceId=r1",
            headers=user_headers,
        )
        assert resp.status_code == 403
        resources_service.preview_cascade_targets.assert_not_called()

    def test_admin_success_lists_cascaded_resources(self, client, admin_headers, resources_service):
        resources_service.preview_cascade_targets.return_value = [
            _fake_dependency(rid="llm-1", name="My LLM", category="llms"),
        ]

        resp = client.get(
            "/api/resources/builtin.cascade-preview?resourceId=r1",
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["cascaded_resources"] == [
            {"rid": "llm-1", "name": "My LLM", "category": "llms"},
        ]

    def test_not_found_returns_404(self, client, admin_headers, resources_service):
        resources_service.preview_cascade_targets.side_effect = KeyError("r1")

        resp = client.get(
            "/api/resources/builtin.cascade-preview?resourceId=r1",
            headers=admin_headers,
        )

        assert resp.status_code == 404


class TestPromoteResource:
    def test_requires_admin(self, client, user_headers, resources_service):
        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=user_headers,
        )
        assert resp.status_code == 403
        resources_service.promote_with_cascade.assert_not_called()

    def test_admin_success(self, client, admin_headers, resources_service):
        resources_service.promote_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 200

    def test_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service, collaboration_service,
    ):
        holder = Mock(user_id="other-admin", display_name="Other Admin")
        collaboration_service.get_admin_edit_lock.return_value = holder

        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 409
        resources_service.promote_with_cascade.assert_not_called()

    def test_allowed_when_lock_held_by_self(
        self, client, admin_headers, resources_service, collaboration_service,
    ):
        from tests.integration.endpoints.conftest import ADMIN_USER

        holder = Mock(user_id=ADMIN_USER, display_name="Admin Alice")
        collaboration_service.get_admin_edit_lock.return_value = holder
        resources_service.promote_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 200

    def test_allowed_when_collaboration_service_unavailable(
        self, client, admin_headers, resources_service, container,
    ):
        container.collaboration_service = None
        resources_service.promote_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 200

    def test_reports_cascaded_dependencies(self, client, admin_headers, resources_service):
        """The nested LLM/provider/tool an agent aggregates gets swept along
        when the agent is promoted — surfaced as ``cascaded_resources``."""
        resources_service.promote_with_cascade.return_value = (
            _fake_resource_dump(),
            [_fake_dependency(rid="llm-1", name="My LLM", category="llms")],
        )

        resp = client.patch(
            "/api/resources/resource.promote",
            json={"resourceId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["cascaded_resources"] == [
            {"rid": "llm-1", "name": "My LLM", "category": "llms"},
        ]


class TestCreateBuiltinResource:
    def test_requires_admin(self, client, user_headers, resources_service):
        resp = client.post(
            "/api/resources/builtin.create",
            json={"category": "provider", "type": "mcp", "name": "n", "config": {}},
            headers=user_headers,
        )
        assert resp.status_code == 403
        resources_service.create_builtin_with_cascade.assert_not_called()

    def test_admin_success(self, client, admin_headers, resources_service):
        resources_service.create_builtin_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.post(
            "/api/resources/builtin.create",
            json={"category": "provider", "type": "mcp", "name": "n", "config": {}},
            headers=admin_headers,
        )

        assert resp.status_code == 201

    def test_available_to_all_reports_cascaded_dependencies(self, client, admin_headers, resources_service):
        resources_service.create_builtin_with_cascade.return_value = (
            _fake_resource_dump(),
            [_fake_dependency(rid="llm-2", name="Backing LLM", category="llms")],
        )

        resp = client.post(
            "/api/resources/builtin.create",
            json={
                "category": "nodes", "type": "deep_agent_node", "name": "n",
                "config": {}, "availableToAll": True,
            },
            headers=admin_headers,
        )

        assert resp.status_code == 201
        assert resp.get_json()["cascaded_resources"] == [
            {"rid": "llm-2", "name": "Backing LLM", "category": "llms"},
        ]


class TestUpdateBuiltinResource:
    def test_requires_admin(self, client, user_headers, resources_service):
        resp = client.put(
            "/api/resources/builtin.update",
            json={"resourceId": "r1", "name": "renamed"},
            headers=user_headers,
        )
        assert resp.status_code == 403
        resources_service.update_builtin_with_cascade.assert_not_called()

    def test_admin_success(self, client, admin_headers, resources_service):
        resources_service.update_builtin_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.put(
            "/api/resources/builtin.update",
            json={"resourceId": "r1", "name": "renamed"},
            headers=admin_headers,
        )

        assert resp.status_code == 200

    def test_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service, collaboration_service,
    ):
        collaboration_service.get_admin_edit_lock.return_value = Mock(
            user_id="other-admin", display_name="Other Admin",
        )

        resp = client.put(
            "/api/resources/builtin.update",
            json={"resourceId": "r1", "name": "renamed"},
            headers=admin_headers,
        )

        assert resp.status_code == 409
        resources_service.update_builtin_with_cascade.assert_not_called()


class TestToggleBuiltinVisibility:
    def test_requires_admin(self, client, user_headers, resources_service):
        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": True},
            headers=user_headers,
        )
        assert resp.status_code == 403

    def test_admin_success(self, client, admin_headers, resources_service):
        resources_service.toggle_visibility_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": True},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        resources_service.toggle_visibility_with_cascade.assert_called_once_with("r1", available_to_all=True)

    def test_turning_on_reports_cascaded_dependencies(self, client, admin_headers, resources_service):
        resources_service.toggle_visibility_with_cascade.return_value = (
            _fake_resource_dump(),
            [_fake_dependency(rid="provider-1", name="My MCP Provider", category="providers")],
        )

        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": True},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["cascaded_resources"] == [
            {"rid": "provider-1", "name": "My MCP Provider", "category": "providers"},
        ]

    def test_turning_off_reports_no_cascade(self, client, admin_headers, resources_service):
        resources_service.toggle_visibility_with_cascade.return_value = (_fake_resource_dump(), [])

        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": False},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert "cascaded_resources" not in resp.get_json()

    def test_blocked_when_locked_by_another_admin(
        self, client, admin_headers, resources_service, collaboration_service,
    ):
        collaboration_service.get_admin_edit_lock.return_value = Mock(
            user_id="other-admin", display_name="Other Admin",
        )

        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": True},
            headers=admin_headers,
        )

        assert resp.status_code == 409
        resources_service.toggle_visibility_with_cascade.assert_not_called()

    def test_turning_off_blocked_by_public_dependents(self, client, admin_headers, resources_service):
        """A leaf still used by a public 'available to all' agent can't be
        demoted — the admin must demote the agent(s) or repoint them first."""
        error = BuiltinDependentsPublicError(
            resource_name="My LLM",
            category="llms",
            dependents=[_fake_dependency(rid="agent-1", name="Research Assistant", category="nodes")],
        )
        resources_service.toggle_visibility_with_cascade.side_effect = error

        resp = client.patch(
            "/api/resources/builtin.toggle",
            json={"resourceId": "r1", "availableToAll": False},
            headers=admin_headers,
        )

        assert resp.status_code == 400
        body = resp.get_json()
        assert "Research Assistant" in body["error"]
        assert body["dependents"] == [
            {"rid": "agent-1", "name": "Research Assistant", "category": "nodes"},
        ]


class TestAdminEditLocks:
    def test_acquire_without_collaboration_service_returns_501(
        self, client, admin_headers, container,
    ):
        container.collaboration_service = None

        resp = client.post(
            "/api/resources/builtin.edit_lock.acquire",
            json={"entityId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 501

    def test_acquire_requires_admin(self, client, user_headers, collaboration_service):
        resp = client.post(
            "/api/resources/builtin.edit_lock.acquire",
            json={"entityId": "r1"},
            headers=user_headers,
        )
        assert resp.status_code == 403
        collaboration_service.acquire_admin_edit_lock.assert_not_called()

    def test_acquire_success(self, client, admin_headers, collaboration_service):
        collaboration_service.acquire_admin_edit_lock.return_value = (True, None)

        resp = client.post(
            "/api/resources/builtin.edit_lock.acquire",
            json={"entityId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 200
        assert resp.get_json()["acquired"] is True

    def test_acquire_unexpected_error_logged_and_returns_500(
        self, client, admin_headers, collaboration_service,
    ):
        """Regression test: unexpected errors in edit-lock handlers must be
        logged (not silently swallowed) and still degrade to a 500."""
        collaboration_service.acquire_admin_edit_lock.side_effect = RuntimeError("redis down")

        resp = client.post(
            "/api/resources/builtin.edit_lock.acquire",
            json={"entityId": "r1"},
            headers=admin_headers,
        )

        assert resp.status_code == 500
        assert resp.get_json()["error"] == "Internal server error"
