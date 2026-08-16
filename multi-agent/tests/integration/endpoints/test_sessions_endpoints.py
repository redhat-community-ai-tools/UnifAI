"""Integration tests for /session.user.list in ``sessions.py``.

Regression coverage for the ``filters`` query param: it arrives as a JSON
string (e.g. from ``use-public-chat.ts``), and must be parsed + allowlisted
before reaching ``session_service`` / the Mongo adapter, which dict-unpack it
via ``**filters``. Previously nothing parsed the string, so a real filter
value raised an unhandled ``TypeError`` (surfaced as a 500).
"""
import json
from unittest.mock import Mock

from flask.testing import FlaskClient


class TestListUserSessionsFilters:
    def test_valid_filters_are_parsed_and_forwarded_as_dict(self, client, user_headers, session_service) -> None:
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps({"blueprint_id": "bp-123"}),
            headers=user_headers,
        )

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == {"blueprint_id": "bp-123"}

    def test_no_filters_forwards_empty_dict(self, client, user_headers, session_service) -> None:
        resp = client.get("/api/sessions/session.user.list", headers=user_headers)

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == {}

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
        assert args[1] == {"blueprint_id": "bp-123"}


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
