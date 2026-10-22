"""Integration tests for /session.user.list in ``sessions.py``.

Regression coverage for the ``filters`` query param: it arrives as a JSON
string (e.g. from ``use-public-chat.ts``), and must be parsed, validated, and
allowlisted into a typed ``SessionListFilter`` before reaching
``session_service`` / the Mongo adapter (which renders it to a ``$match``
fragment). Previously nothing parsed the string, so a real filter value
raised an unhandled ``TypeError`` (surfaced as a 500).
"""
import json
from unittest.mock import Mock

import pytest
from flask.testing import FlaskClient

from mas.session.domain.dto import SessionListFilter
from mas.session.domain.exceptions import SessionBuildError


class TestListUserSessionsFilters:
    def test_valid_filters_are_parsed_and_forwarded_as_typed_model(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps({"blueprint_id": "bp-123"}),
            headers=user_headers,
        )

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == SessionListFilter(blueprint_id="bp-123")

    def test_no_filters_forwards_empty_typed_model(self, client, user_headers, session_service) -> None:
        resp = client.get("/api/sessions/session.user.list", headers=user_headers)

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == SessionListFilter()

    def test_malformed_json_returns_400(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?filters=not-json",
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_non_object_json_returns_400(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps(["blueprint_id", "bp-123"]),
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_unknown_filter_key_returns_400(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps({"$where": "1==1"}),
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_operator_filter_value_returns_400(self, client, user_headers, session_service) -> None:
        # An allowlisted key with a non-string value would smuggle a MongoDB
        # query operator into the $match document; values must be rejected too.
        resp = client.get(
            "/api/sessions/session.user.list?filters="
            + json.dumps({"blueprint_id": {"$ne": None}}),
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_parsed_filters_are_also_passed_to_count_when_paginated(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?limit=10&offset=0&filters="
            + json.dumps({"blueprint_id": "bp-123"}),
            headers=user_headers,
        )

        assert resp.status_code == 200
        args, _ = session_service.count.call_args
        assert args[1] == SessionListFilter(blueprint_id="bp-123")


class TestListUserSessionsLegacyContract:
    """Regression coverage for legacy callers (e.g. the Slack /sessions command)
    that omit limit/offset and expect the full, unpaginated session array.

    webargs' load_default=50 on the `limit` field means the handler's local
    `limit` variable is never None, so the service call must be gated on
    whether the client actually requested pagination rather than on that
    defaulted value — otherwise legacy callers get silently truncated to 50.
    """

    def test_no_pagination_params_requests_unlimited_sessions(self, client, user_headers, session_service) -> None:
        resp = client.get("/api/sessions/session.user.list", headers=user_headers)

        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["limit"] is None

    def test_explicit_limit_is_forwarded_and_triggers_paginated_envelope(self, client, user_headers, session_service) -> None:
        resp = client.get("/api/sessions/session.user.list?limit=10", headers=user_headers)

        assert resp.status_code == 200
        assert "pagination" in resp.get_json()
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["limit"] == 10

    def test_explicit_offset_without_limit_still_paginates_with_default_limit(self, client, user_headers, session_service) -> None:
        resp = client.get("/api/sessions/session.user.list?offset=20", headers=user_headers)

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["pagination"]["limit"] == 50
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["limit"] == 50
        assert kwargs["offset"] == 20


class TestListUserSessionsHasMore:
    """Regression coverage for the ``has_more`` pagination flag.

    The frontend drives infinite scrolling from this single field:
    ``getNextPageParam`` in ``use-session-hub.ts`` and ``use-public-chat.ts``
    stops paging when ``has_more`` is false. A regression in
    ``offset + limit < total`` therefore either truncates the session list
    (stops early) or loops forever (never stops), so both boundaries are
    asserted here.
    """

    def test_has_more_true_when_more_pages_remain(self, client: FlaskClient, user_headers: dict[str, str], session_service: Mock) -> None:
        # offset(0) + limit(10) < total(25): another page exists.
        session_service.count.return_value = 25
        resp = client.get("/api/sessions/session.user.list?limit=10&offset=0", headers=user_headers)

        assert resp.status_code == 200
        pagination = resp.get_json()["pagination"]
        assert pagination["total"] == 25
        assert pagination["has_more"] is True

    def test_has_more_false_on_last_page(self, client: FlaskClient, user_headers: dict[str, str], session_service: Mock) -> None:
        # offset(20) + limit(10) >= total(25): this is the final page.
        session_service.count.return_value = 25
        resp = client.get("/api/sessions/session.user.list?limit=10&offset=20", headers=user_headers)

        assert resp.status_code == 200
        pagination = resp.get_json()["pagination"]
        assert pagination["total"] == 25
        assert pagination["has_more"] is False

    def test_has_more_false_when_offset_plus_limit_exactly_equals_total(self, client: FlaskClient, user_headers: dict[str, str], session_service: Mock) -> None:
        # Exact boundary: offset(10) + limit(10) == total(20), nothing remains.
        session_service.count.return_value = 20
        resp = client.get("/api/sessions/session.user.list?limit=10&offset=10", headers=user_headers)

        assert resp.status_code == 200
        assert resp.get_json()["pagination"]["has_more"] is False


class TestExecuteSessionBuildFailure:
    """A session whose elements cannot be built must fail cleanly, not as a raw HTML 500."""

    BODY = {"sessionId": "s-1", "inputs": {"query": "hi"}}

    @pytest.fixture(autouse=True)
    def _bypass_session_checks(self, monkeypatch) -> None:
        monkeypatch.setattr("inbound.flask.session_access.authorize_session", lambda sid: (Mock(), None))
        monkeypatch.setattr("inbound.flask.endpoints.sessions._check_session_busy", lambda *a, **k: None)
        monkeypatch.setattr("inbound.flask.endpoints.sessions._bind_forwarded_identity", lambda *a, **k: None)

    def _post(self, client, headers, **extra):
        return client.post("/api/sessions/user.session.execute", json={**self.BODY, **extra}, headers=headers)

    @pytest.mark.parametrize("stream", [True, False])
    def test_build_failure_returns_structured_json_error(self, client, user_headers, session_service, stream) -> None:
        session_service.run.side_effect = SessionBuildError("s-1", "Session build failed (PluginConfigurationError): bad tool")

        resp = self._post(client, user_headers, stream=stream)

        assert resp.status_code == 500
        assert resp.mimetype == "application/json"
        assert resp.get_json() == {
            "error": "Session build failed (PluginConfigurationError): bad tool",
            "error_type": "session_build_failed",
            "sessionId": "s-1",
        }

    def test_build_failure_body_never_carries_config(self, client, user_headers, session_service) -> None:
        err = SessionBuildError("s-1", "MemoryToolFactory.create() failed: [Errno 111] refused | config={'qdrant_url': 'http://u:pw@qdrant.internal:6333'}")
        session_service.run.side_effect = err

        resp = self._post(client, user_headers)

        assert resp.status_code == 500
        body = resp.get_data(as_text=True)
        assert "config=" not in body and "qdrant" not in body and "pw@" not in body

    def test_build_failure_is_raised_before_the_stream_starts(self, client, user_headers, session_service) -> None:
        session_service.run.side_effect = SessionBuildError("s-1", "boom")

        resp = self._post(client, user_headers, stream=True)

        assert resp.mimetype != "application/x-ndjson"
        assert "<html" not in resp.get_data(as_text=True).lower()

    def test_build_failure_inside_the_stream_becomes_an_ndjson_error_event(self, client, user_headers, session_service) -> None:
        def broken():
            raise SessionBuildError("s-1", "boom")
            yield  # pragma: no cover

        session_service.run.return_value = broken()

        resp = self._post(client, user_headers, stream=True)

        assert resp.status_code == 200
        lines = [json.loads(line) for line in resp.get_data(as_text=True).splitlines() if line.strip()]
        assert lines[-1] == {"error": "boom", "error_type": "session_build_failed", "sessionId": "s-1"}

    def test_successful_stream_is_unchanged(self, client, user_headers, session_service) -> None:
        session_service.run.return_value = iter([{"event": "a"}])

        resp = self._post(client, user_headers, stream=True)

        assert resp.mimetype == "application/x-ndjson"
        assert json.loads(resp.get_data(as_text=True).splitlines()[0]) == {"event": "a"}


class TestSubmitSession:
    BODY = {"sessionId": "s-1", "inputs": {"query": "hi"}}

    @pytest.fixture(autouse=True)
    def _bypass_session_checks(self, monkeypatch) -> None:
        monkeypatch.setattr("inbound.flask.session_access.authorize_session", lambda sid: (Mock(), None))
        monkeypatch.setattr("inbound.flask.endpoints.sessions._check_session_busy", lambda *a, **k: None)
        monkeypatch.setattr("inbound.flask.endpoints.sessions._bind_forwarded_identity", lambda *a, **k: None)

    def _post(self, client, headers):
        return client.post("/api/sessions/user.session.submit", json=self.BODY, headers=headers)

    def test_normal_path_returns_202(self, client, user_headers, session_service) -> None:
        session_service.submit.return_value = "wf-1"

        resp = self._post(client, user_headers)

        assert resp.status_code == 202
        assert resp.get_json() == {"sessionId": "s-1", "workflowId": "wf-1"}

    def test_build_failure_body_never_carries_config(self, client, user_headers, session_service) -> None:
        err = SessionBuildError("s-1", "MemoryToolFactory.create() failed: [Errno 111] refused | config={'qdrant_url': 'http://u:pw@qdrant.internal:6333'}")
        session_service.submit.side_effect = err

        resp = self._post(client, user_headers)

        assert resp.status_code == 500
        body = resp.get_data(as_text=True)
        assert "config=" not in body and "qdrant" not in body and "pw@" not in body

    def test_build_failure_returns_structured_error_without_config(self, client, user_headers, session_service) -> None:
        session_service.submit.side_effect = SessionBuildError("s-1", "Session build failed (PluginConfigurationError): bad tool")

        resp = self._post(client, user_headers)

        assert resp.status_code == 500
        assert resp.get_json() == {
            "error": "Session build failed (PluginConfigurationError): bad tool",
            "error_type": "session_build_failed",
            "sessionId": "s-1",
        }
