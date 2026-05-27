"""Sessions API — create, execute, and query workflow sessions."""
from __future__ import annotations

from typing import Any, Optional

from unifai_cli.api.base import MASClient

# Auth requirements per multi-agent/adapters/inbound/flask/endpoints/sessions.py
# (all auth endpoints now use @with_require_team_session — X-Session-Id header).
#
# CLI method              | Backend route              | Requires session
# ------------------------|----------------------------|-----------------
# create_session          | user.session.create        | YES
# submit_session          | user.session.submit        | YES
# execute_session         | user.session.execute       | YES
# run_session_turn        | submit + session.subscribe | YES on submit only
# get_session_chat        | session.chat.get           | NO
# get_session_status      | session.status.get         | NO
# get_stream_status       | session.stream.status      | NO
# subscribe_session       | session.subscribe          | NO


class SessionsAPI(MASClient):
    """API methods for workflow sessions."""

    def _require_user_id(self, user_id: Optional[str] = None) -> str:
        uid = self._effective_user_id(user_id)
        if not uid:
            raise ValueError(
                "Authenticated user is required. Call build_client(..., user_id=...) "
                "or client.set_authenticated_user() before session API calls."
            )
        return uid

    def _identity_body(self, user_id: Optional[str] = None) -> dict[str, str]:
        """Body ``userId`` for @with_require_identity_authorization endpoints."""
        return {"userId": self._require_user_id(user_id)}

    def create_session(self, user_id: str, blueprint_id: str,
                       metadata: Optional[dict] = None) -> str:
        """POST /sessions/user.session.create — identity auth required."""
        uid = self._require_user_id(user_id)
        body: dict[str, Any] = {
            "blueprintId": blueprint_id,
            **self._identity_body(uid),
        }
        if metadata:
            body["metadata"] = metadata
        return self._post(
            "sessions",
            "user.session.create",
            json=body,
            user_id=uid,
        )

    def submit_session(self, session_id: str, inputs: dict,
                       scope: str = "public", user_id: Optional[str] = None,
                       session_type: str = "Personal") -> dict:
        """POST /sessions/user.session.submit — identity auth required, HTTP 202."""
        uid = self._require_user_id(user_id)
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "scope": scope,
            "sessionType": session_type,
            **self._identity_body(uid),
        }
        return self._post("sessions", "user.session.submit", json=body, user_id=uid)

    def execute_session(self, session_id: str, inputs: dict,
                        stream: bool = False, scope: str = "public",
                        user_id: Optional[str] = None,
                        session_type: str = "Personal"):
        """POST /sessions/user.session.execute — identity auth required."""
        uid = self._require_user_id(user_id)
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": stream,
            "scope": scope,
            "streamMode": ["custom"],
            "sessionType": session_type,
            **self._identity_body(uid),
        }
        if stream:
            return self._post_stream(
                "sessions", "user.session.execute", json=body, user_id=uid,
            )
        return self._post("sessions", "user.session.execute", json=body, user_id=uid)

    def run_session_turn(self, session_id: str, inputs: dict,
                         scope: str = "public", user_id: Optional[str] = None):
        """
        Run one workflow turn the same way as the UI on Temporal/Redis backends:
        POST /user.session.submit then GET /session.subscribe (NDJSON).
        """
        self.submit_session(session_id, inputs, scope=scope, user_id=user_id)
        return self.subscribe_session(session_id)

    def get_session_chat(self, session_id: str) -> dict:
        """GET /sessions/session.chat.get — no identity auth."""
        return self._get(
            "sessions",
            "session.chat.get",
            params={"sessionId": session_id},
        )

    def get_session_status(self, session_id: str) -> dict:
        """GET /sessions/session.status.get — no identity auth."""
        return self._get(
            "sessions",
            "session.status.get",
            params={"sessionId": session_id},
        )

    def get_stream_status(self, session_id: str) -> dict:
        """GET /sessions/session.stream.status — no identity auth."""
        return self._get(
            "sessions",
            "session.stream.status",
            params={"sessionId": session_id},
        )

    def subscribe_session(self, session_id: str):
        """GET /sessions/session.subscribe — NDJSON, no identity auth."""
        return self._get_stream(
            "sessions",
            "session.subscribe",
            params={"sessionId": session_id},
        )
