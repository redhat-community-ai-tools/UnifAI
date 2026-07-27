"""Sessions API — create, execute, and query workflow sessions."""
from __future__ import annotations

from typing import Any, Optional

from unifai_cli.api.base import MASClient

# Auth requirements per multi-agent/adapters/inbound/flask/endpoints/sessions.py
# Authentication is via the session cookie (validated server-side against Redis).
# The backend resolves the caller's identity from the cookie — no userId needed.


class SessionsAPI(MASClient):
    """API methods for workflow sessions."""

    def create_session(self, blueprint_id: str,
                       metadata: Optional[dict] = None) -> str:
        """POST /sessions/user.session.create"""
        body: dict[str, Any] = {"blueprintId": blueprint_id}
        if metadata:
            body["metadata"] = metadata
        return self._post("sessions", "user.session.create", json=body)

    def submit_session(self, session_id: str, inputs: dict,
                       scope: str = "public",
                       session_type: str = "Personal") -> dict:
        """POST /sessions/user.session.submit"""
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "scope": scope,
            "sessionType": session_type,
        }
        return self._post("sessions", "user.session.submit", json=body)

    def execute_session(self, session_id: str, inputs: dict,
                        stream: bool = False, scope: str = "public",
                        session_type: str = "Personal"):
        """POST /sessions/user.session.execute"""
        body = {
            "sessionId": session_id,
            "inputs": inputs,
            "stream": stream,
            "scope": scope,
            "streamMode": ["custom"],
            "sessionType": session_type,
        }
        if stream:
            return self._post_stream(
                "sessions", "user.session.execute", json=body,
            )
        return self._post("sessions", "user.session.execute", json=body)

    def run_session_turn(self, session_id: str, inputs: dict,
                         scope: str = "public"):
        """Submit then subscribe (same flow as the UI)."""
        self.submit_session(session_id, inputs, scope=scope)
        return self.subscribe_session(session_id)

    def get_session_chat(self, session_id: str) -> dict:
        """GET /sessions/session.chat.get"""
        return self._get(
            "sessions",
            "session.chat.get",
            params={"sessionId": session_id},
        )

    def get_session_status(self, session_id: str) -> dict:
        """GET /sessions/session.status.get"""
        return self._get(
            "sessions",
            "session.status.get",
            params={"sessionId": session_id},
        )

    def get_stream_status(self, session_id: str) -> dict:
        """GET /sessions/session.stream.status"""
        return self._get(
            "sessions",
            "session.stream.status",
            params={"sessionId": session_id},
        )

    def subscribe_session(self, session_id: str):
        """GET /sessions/session.subscribe — NDJSON stream."""
        return self._get_stream(
            "sessions",
            "session.subscribe",
            params={"sessionId": session_id},
        )
