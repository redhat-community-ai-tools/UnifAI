"""Integration tests for /session.user.list in ``sessions.py``.

Regression coverage for the ``filters`` query param: it arrives as a JSON
string (e.g. from ``use-public-chat.ts``), and must be parsed + allowlisted
before reaching ``session_service`` / the Mongo adapter, which dict-unpack it
via ``**filters``. Previously nothing parsed the string, so a real filter
value raised an unhandled ``TypeError`` (surfaced as a 500).
"""
import json


class TestListUserSessionsFilters:
    def test_valid_filters_are_parsed_and_forwarded_as_dict(self, client, user_headers, session_service):
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps({"blueprint_id": "bp-123"}),
            headers=user_headers,
        )

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == {"blueprint_id": "bp-123"}

    def test_no_filters_forwards_empty_dict(self, client, user_headers, session_service):
        resp = client.get("/api/sessions/session.user.list", headers=user_headers)

        assert resp.status_code == 200
        _, kwargs = session_service.list_user_sessions.call_args
        assert kwargs["filters"] == {}

    def test_malformed_json_returns_400(self, client, user_headers, session_service):
        resp = client.get(
            "/api/sessions/session.user.list?filters=not-json",
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_non_object_json_returns_400(self, client, user_headers, session_service):
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps(["blueprint_id", "bp-123"]),
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_unknown_filter_key_returns_400(self, client, user_headers, session_service):
        resp = client.get(
            "/api/sessions/session.user.list?filters=" + json.dumps({"$where": "1==1"}),
            headers=user_headers,
        )

        assert resp.status_code == 400
        session_service.list_user_sessions.assert_not_called()

    def test_parsed_filters_are_also_passed_to_count_when_paginated(self, client, user_headers, session_service):
        resp = client.get(
            "/api/sessions/session.user.list?limit=10&offset=0&filters="
            + json.dumps({"blueprint_id": "bp-123"}),
            headers=user_headers,
        )

        assert resp.status_code == 200
        args, _ = session_service.count.call_args
        assert args[1] == {"blueprint_id": "bp-123"}
