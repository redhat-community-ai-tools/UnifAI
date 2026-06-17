"""
Integration tests for Blueprint Version History API endpoints — GENIE-1336.

Strategy
--------
A minimal Flask test app is assembled here (no real DB, no real identity
provider) so that the HTTP layer — routing, query-param parsing, body
parsing, error mapping, and JSON serialisation — can be verified without
touching the service logic.

The ``blueprint_service`` on the container is a fresh ``MagicMock`` for
every test (via the ``autouse`` ``mock_svc`` fixture), which lets each test
configure exactly the return value / side effect it needs.

The ``@with_authenticated_user`` decorator is exercised by including the
``X-Authenticated-User`` header in requests; when
``container.identity_provider.requires_authentication`` is ``False`` the
header is optional.

Covers
------
  - GET  /blueprint.versions.list  : 200 (paginated), 404 (blueprint), 500
  - GET  /blueprint.version.get    : 200 (full detail), 404 (blueprint),
                                     404 (version), 500
  - POST /blueprint.version.restore: 200, 404 (blueprint), 404 (version),
                                     409 (ConcurrentModification), 500, 401
  - Regression: PUT /blueprint.update does NOT forward user_id to
    update_draft() — the snapshot will have an empty created_by field
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, call

from mas.blueprints.exceptions import (
    BlueprintNotFoundError,
    VersionNotFoundError,
    ConcurrentModificationError,
)


# ── App & Client fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def app():
    """Minimal Flask application wired with a mock container.

    Scoped to *module* so the Flask app object is created once per module —
    only the ``blueprint_service`` attribute on the container is swapped out
    before each test via ``mock_svc``.
    """
    from flask import Flask
    from adapters.inbound.flask.endpoints.blueprints import blueprints_bp

    flask_app = Flask(__name__)
    flask_app.register_blueprint(blueprints_bp)

    # Identity provider mock: requires_authentication=False so tests that
    # don't supply the header are still served (no stray 401s).
    container = MagicMock()
    container.identity_provider.requires_authentication = False
    flask_app.container = container

    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture(scope="module")
def client(app):
    """Flask test client shared across the module."""
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_svc(app):
    """Replace ``blueprint_service`` on the container before every test.

    The ``autouse=True`` means every test gets a fresh, unconfigured mock.
    Tests can receive this fixture by name to set return values / side effects.
    """
    svc = MagicMock()
    app.container.blueprint_service = svc
    return svc


# ── Helpers ───────────────────────────────────────────────────────────────────

_AUTH_HEADER = {"X-Authenticated-User": "test-user"}
_JSON_HEADER = {"Content-Type": "application/json"}
_RESTORE_HEADERS = {**_AUTH_HEADER, **_JSON_HEADER}


def _post_restore(client, blueprint_id: str, version: int, headers=None):
    """POST /blueprint.version.restore helper."""
    return client.post(
        "/blueprint.version.restore",
        data=json.dumps({"blueprintId": blueprint_id, "version": version}),
        headers=headers or _RESTORE_HEADERS,
    )


# ── GET /blueprint.versions.list ──────────────────────────────────────────────


@pytest.mark.integration
class TestListBlueprintVersionsEndpoint:
    """Tests for GET /blueprint.versions.list."""

    def test_happy_path_returns_200(self, client, mock_svc):
        """Successful list returns 200 with the service payload verbatim."""
        payload = {
            "items": [
                {
                    "version": 2,
                    "created_by": "u1",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "change_summary": None,
                }
            ],
            "total": 2,
            "page": 1,
            "page_size": 20,
            "total_pages": 1,
        }
        mock_svc.list_versions.return_value = payload

        resp = client.get("/blueprint.versions.list?blueprintId=bp-123")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 2
        assert len(data["items"]) == 1

    def test_service_receives_correct_blueprint_id(self, client, mock_svc):
        """The blueprintId query param is forwarded to the service unchanged."""
        mock_svc.list_versions.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0
        }

        client.get("/blueprint.versions.list?blueprintId=bp-abc")

        mock_svc.list_versions.assert_called_once_with(
            blueprint_id="bp-abc", page=1, page_size=20
        )

    def test_default_pagination_params(self, client, mock_svc):
        """When page/pageSize are omitted, defaults (page=1, page_size=20) are used."""
        mock_svc.list_versions.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0
        }

        client.get("/blueprint.versions.list?blueprintId=bp-1")

        _, kwargs = mock_svc.list_versions.call_args
        assert kwargs["page"] == 1
        assert kwargs["page_size"] == 20

    def test_custom_pagination_params_forwarded(self, client, mock_svc):
        """Explicit page and pageSize query params reach the service."""
        mock_svc.list_versions.return_value = {
            "items": [], "total": 50, "page": 3, "page_size": 10, "total_pages": 5
        }

        client.get("/blueprint.versions.list?blueprintId=bp-1&page=3&pageSize=10")

        mock_svc.list_versions.assert_called_once_with(
            blueprint_id="bp-1", page=3, page_size=10
        )

    def test_blueprint_not_found_returns_404(self, client, mock_svc):
        """BlueprintNotFoundError is mapped to HTTP 404."""
        mock_svc.list_versions.side_effect = BlueprintNotFoundError("bp-ghost")

        resp = client.get("/blueprint.versions.list?blueprintId=bp-ghost")

        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_runtime_error_version_repo_not_configured_returns_500(self, client, mock_svc):
        """RuntimeError (version_repo not wired) is surfaced as 500."""
        mock_svc.list_versions.side_effect = RuntimeError("version_repo is not configured")

        resp = client.get("/blueprint.versions.list?blueprintId=bp-1")

        assert resp.status_code == 500
        assert "error" in resp.get_json()

    def test_response_contains_all_required_envelope_keys(self, client, mock_svc):
        """Every 200 response must carry items, total, page, page_size, total_pages."""
        mock_svc.list_versions.return_value = {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 20,
            "total_pages": 0,
        }

        resp = client.get("/blueprint.versions.list?blueprintId=bp-xyz")

        assert resp.status_code == 200
        data = resp.get_json()
        for key in ("items", "total", "page", "page_size", "total_pages"):
            assert key in data, f"Response envelope is missing key '{key}'"

    def test_items_list_present_when_empty(self, client, mock_svc):
        """An empty blueprint with zero versions returns items=[] (not null)."""
        mock_svc.list_versions.return_value = {
            "items": [], "total": 0, "page": 1, "page_size": 20, "total_pages": 0
        }

        resp = client.get("/blueprint.versions.list?blueprintId=bp-new")

        assert resp.status_code == 200
        assert resp.get_json()["items"] == []

    def test_unexpected_exception_returns_500(self, client, mock_svc):
        """An uncaught exception from the service is caught and returned as 500."""
        mock_svc.list_versions.side_effect = Exception("database is on fire")

        resp = client.get("/blueprint.versions.list?blueprintId=bp-1")

        assert resp.status_code == 500


# ── GET /blueprint.version.get ────────────────────────────────────────────────


@pytest.mark.integration
class TestGetBlueprintVersionEndpoint:
    """Tests for GET /blueprint.version.get."""

    def _detail(self, **overrides) -> dict:
        base = {
            "blueprint_id": "bp-1",
            "version": 3,
            "created_by": "alice",
            "created_at": "2026-06-10T12:00:00+00:00",
            "change_summary": "Added new node",
            "spec_dict_snapshot": {"nodes": [{"id": "n1"}]},
        }
        base.update(overrides)
        return base

    def test_happy_path_returns_200_with_full_detail(self, client, mock_svc):
        """Successful fetch returns 200 with the full version detail dict."""
        mock_svc.load_version.return_value = self._detail()

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=3")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["version"] == 3
        assert data["spec_dict_snapshot"] == {"nodes": [{"id": "n1"}]}

    def test_service_receives_correct_args(self, client, mock_svc):
        """blueprint_id and version are correctly forwarded to load_version()."""
        mock_svc.load_version.return_value = self._detail(blueprint_id="bp-7", version=5)

        client.get("/blueprint.version.get?blueprintId=bp-7&version=5")

        mock_svc.load_version.assert_called_once_with(blueprint_id="bp-7", version_number=5)

    def test_response_includes_spec_dict_snapshot(self, client, mock_svc):
        """The response body must include the full spec_dict_snapshot."""
        spec = {"nodes": [{"id": "n1"}, {"id": "n2"}], "edges": [{"from": "n1", "to": "n2"}]}
        mock_svc.load_version.return_value = self._detail(spec_dict_snapshot=spec)

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=3")

        assert resp.status_code == 200
        assert resp.get_json()["spec_dict_snapshot"] == spec

    def test_response_includes_all_detail_keys(self, client, mock_svc):
        """Every field of the version detail is present in the 200 response."""
        mock_svc.load_version.return_value = self._detail()

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=3")

        data = resp.get_json()
        for key in ("blueprint_id", "version", "created_by", "created_at",
                    "change_summary", "spec_dict_snapshot"):
            assert key in data, f"Detail key '{key}' missing from response"

    def test_blueprint_not_found_returns_404(self, client, mock_svc):
        """BlueprintNotFoundError → 404."""
        mock_svc.load_version.side_effect = BlueprintNotFoundError("bp-ghost")

        resp = client.get("/blueprint.version.get?blueprintId=bp-ghost&version=1")

        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_version_not_found_returns_404(self, client, mock_svc):
        """VersionNotFoundError → 404."""
        mock_svc.load_version.side_effect = VersionNotFoundError("bp-1", 99)

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=99")

        assert resp.status_code == 404
        data = resp.get_json()
        assert "error" in data
        # Error message must contain version info
        assert "99" in data["error"]

    def test_version_not_found_error_message_contains_blueprint_id(self, client, mock_svc):
        """VersionNotFoundError message must reference the blueprint ID."""
        mock_svc.load_version.side_effect = VersionNotFoundError("bp-owned", 5)

        resp = client.get("/blueprint.version.get?blueprintId=bp-owned&version=5")

        assert "bp-owned" in resp.get_json()["error"]

    def test_runtime_error_returns_500(self, client, mock_svc):
        """RuntimeError (version_repo not configured) → 500."""
        mock_svc.load_version.side_effect = RuntimeError("version_repo is not configured")

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=1")

        assert resp.status_code == 500

    def test_unexpected_exception_returns_500(self, client, mock_svc):
        """Any uncaught exception from the service → 500."""
        mock_svc.load_version.side_effect = Exception("disk full")

        resp = client.get("/blueprint.version.get?blueprintId=bp-1&version=1")

        assert resp.status_code == 500


# ── POST /blueprint.version.restore ──────────────────────────────────────────


@pytest.mark.integration
class TestRestoreBlueprintVersionEndpoint:
    """Tests for POST /blueprint.version.restore."""

    def test_happy_path_returns_200(self, client, mock_svc):
        """Successful restore returns 200 with status+blueprint_id+restored_to_version."""
        mock_svc.restore_version.return_value = True

        resp = _post_restore(client, "bp-1", 2)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "success"
        assert data["blueprint_id"] == "bp-1"
        assert data["restored_to_version"] == 2

    def test_service_receives_correct_blueprint_id_and_version(self, client, mock_svc):
        """blueprint_id and target_version are forwarded correctly."""
        mock_svc.restore_version.return_value = True

        _post_restore(client, "bp-9", 7)

        mock_svc.restore_version.assert_called_once_with(
            blueprint_id="bp-9", target_version=7, user_id="test-user"
        )

    def test_authenticated_user_header_forwarded_as_user_id(self, client, mock_svc):
        """X-Authenticated-User header value becomes the user_id arg."""
        mock_svc.restore_version.return_value = True

        _post_restore(
            client, "bp-1", 3,
            headers={**_AUTH_HEADER, **_JSON_HEADER, "X-Authenticated-User": "alice"},
        )

        _, kwargs = mock_svc.restore_version.call_args
        assert kwargs["user_id"] == "alice"

    def test_blueprint_not_found_returns_404(self, client, mock_svc):
        """BlueprintNotFoundError → 404."""
        mock_svc.restore_version.side_effect = BlueprintNotFoundError("bp-ghost")

        resp = _post_restore(client, "bp-ghost", 1)

        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_version_not_found_returns_404(self, client, mock_svc):
        """VersionNotFoundError → 404."""
        mock_svc.restore_version.side_effect = VersionNotFoundError("bp-1", 99)

        resp = _post_restore(client, "bp-1", 99)

        assert resp.status_code == 404
        assert "99" in resp.get_json()["error"]

    def test_concurrent_modification_returns_409(self, client, mock_svc):
        """ConcurrentModificationError → 409 Conflict."""
        mock_svc.restore_version.side_effect = ConcurrentModificationError("bp-1", 3)

        resp = _post_restore(client, "bp-1", 3)

        assert resp.status_code == 409
        data = resp.get_json()
        assert "error" in data
        # Error must hint at the OCC nature of the failure
        error_lower = data["error"].lower()
        assert "concurrent" in error_lower or "conflict" in error_lower or "modified" in error_lower

    def test_concurrent_modification_error_message_mentions_blueprint(self, client, mock_svc):
        """The 409 body must reference the blueprint ID."""
        mock_svc.restore_version.side_effect = ConcurrentModificationError("bp-targeted", 5)

        resp = _post_restore(client, "bp-targeted", 5)

        assert resp.status_code == 409
        assert "bp-targeted" in resp.get_json()["error"]

    def test_runtime_error_returns_500(self, client, mock_svc):
        """RuntimeError (version_repo not configured) → 500."""
        mock_svc.restore_version.side_effect = RuntimeError("version_repo is not configured")

        resp = _post_restore(client, "bp-1", 1)

        assert resp.status_code == 500
        assert "error" in resp.get_json()

    def test_unexpected_exception_returns_500(self, client, mock_svc):
        """Any uncaught exception → 500."""
        mock_svc.restore_version.side_effect = Exception("uncharted territory")

        resp = _post_restore(client, "bp-1", 1)

        assert resp.status_code == 500

    def test_missing_auth_header_when_auth_required_returns_401(self, app, client, mock_svc):
        """When provider.requires_authentication=True and header is absent → 401."""
        app.container.identity_provider.requires_authentication = True
        try:
            resp = client.post(
                "/blueprint.version.restore",
                data=json.dumps({"blueprintId": "bp-1", "version": 1}),
                headers=_JSON_HEADER,  # No X-Authenticated-User
            )
            assert resp.status_code == 401
        finally:
            # Always restore so subsequent tests are not affected.
            app.container.identity_provider.requires_authentication = False

    def test_restore_success_body_structure(self, client, mock_svc):
        """The 200 body must contain exactly the expected keys."""
        mock_svc.restore_version.return_value = True

        resp = _post_restore(client, "bp-1", 4)

        data = resp.get_json()
        assert set(data.keys()) >= {"status", "blueprint_id", "restored_to_version"}


# ── PUT /blueprint.update — regression: missing user_id passthrough ───────────


@pytest.mark.integration
class TestUpdateBlueprintEndpointRegression:
    """Regression tests that document the known gap in PUT /blueprint.update.

    The endpoint currently calls ``update_draft(blueprint_id=..., draft_dict=...)``
    WITHOUT forwarding a ``user_id`` or ``change_summary``.  When the
    version_repo is active this results in snapshots with ``created_by=""``.
    These tests lock in the current behaviour so any future fix is deliberate.
    """

    _HEADERS = {"Content-Type": "application/json"}
    _BODY = json.dumps({"blueprintId": "bp-1", "blueprintRaw": "name: test\n"})

    def test_update_draft_called_without_user_id(self, client, mock_svc):
        """update_draft() is invoked without a user_id keyword argument."""
        mock_svc.update_draft.return_value = True

        client.put("/blueprint.update", data=self._BODY, headers=self._HEADERS)

        args, kwargs = mock_svc.update_draft.call_args
        assert "user_id" not in kwargs, (
            "user_id was forwarded — the regression test is now obsolete. "
            "Update the endpoint tests to verify correct user_id propagation."
        )

    def test_update_draft_called_without_change_summary(self, client, mock_svc):
        """update_draft() is invoked without a change_summary keyword argument."""
        mock_svc.update_draft.return_value = True

        client.put("/blueprint.update", data=self._BODY, headers=self._HEADERS)

        _, kwargs = mock_svc.update_draft.call_args
        assert "change_summary" not in kwargs, (
            "change_summary was forwarded — the regression test is now obsolete."
        )

    def test_update_returns_200_on_success(self, client, mock_svc):
        """PUT /blueprint.update returns 200 when update_draft() succeeds."""
        mock_svc.update_draft.return_value = True

        resp = client.put("/blueprint.update", data=self._BODY, headers=self._HEADERS)

        assert resp.status_code == 200

    def test_update_returns_404_on_blueprint_not_found(self, client, mock_svc):
        """PUT /blueprint.update returns 404 when the blueprint doesn't exist."""
        mock_svc.update_draft.side_effect = BlueprintNotFoundError("bp-1")

        resp = client.put("/blueprint.update", data=self._BODY, headers=self._HEADERS)

        assert resp.status_code == 404

    def test_update_does_not_return_409_on_concurrent_modification(self, client, mock_svc):
        """ConcurrentModificationError raised by update_draft() is NOT mapped to 409.

        The endpoint catches it via the generic ``except Exception`` handler and
        returns 500.  This is a known gap: the update endpoint does not surface
        the 409 status code that the restore endpoint does.
        """
        mock_svc.update_draft.side_effect = ConcurrentModificationError("bp-1", 2)

        resp = client.put("/blueprint.update", data=self._BODY, headers=self._HEADERS)

        # Not 409 — the gap means callers cannot distinguish OCC from a real 500.
        assert resp.status_code == 500
