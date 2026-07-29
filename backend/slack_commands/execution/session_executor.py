"""SessionExecutor — runs session lifecycle in a background thread.

Handles the deferred-response pattern required by Slack's 3-second limit:
submit → poll → extract answer → POST result to response_url.

This is the single place where the poll/respond logic lives (DRY).
"""
import atexit
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional
from urllib.parse import urlparse

import requests

from slack_commands.http import mas_get, mas_post

logger = logging.getLogger(__name__)

_POLL_INTERVAL = 2
_POLL_TIMEOUT = 600
_TERMINAL_STATUSES = frozenset({"COMPLETED", "FAILED", "CANCELLED"})
_MAX_WORKERS = 10


class SessionExecutor:
    """Executes a session asynchronously and posts the result to Slack."""

    def __init__(self, base_url: str, max_workers: int = _MAX_WORKERS):
        self._url = base_url.rstrip("/")
        self._pool = ThreadPoolExecutor(max_workers=max_workers)
        atexit.register(self.close)

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    def run_new_session(
        self,
        user_name: str,
        workflow_id: str,
        question: str,
        response_url: str = "",
        *,
        public: bool = False,
        team_uid: Optional[str] = None,
        reply_fn=None,
    ) -> None:
        """Submit a background task that creates, submits, polls, and responds."""
        self._pool.submit(
            self._execute, user_name, workflow_id, question, response_url, False, public, team_uid, reply_fn,
        )

    def continue_session(
        self,
        user_name: str,
        session_id: str,
        question: str,
        response_url: str,
        *,
        public: bool = False,
        team_uid: Optional[str] = None,
    ) -> None:
        """Submit a background task that submits to existing session, polls, and responds."""
        self._pool.submit(
            self._execute, user_name, session_id, question, response_url, True, public, team_uid,
        )

    def _execute(
        self,
        user_name: str,
        ref_id: str,
        question: str,
        response_url: str,
        is_continuation: bool,
        public: bool,
        team_uid: Optional[str] = None,
        reply_fn=None,
    ) -> None:
        def _reply(text):
            if reply_fn:
                reply_fn(text)
            else:
                self._post_to_slack(response_url, text, public=public)

        try:
            if is_continuation:
                session_id = ref_id
            else:
                session_id = self._create_session(user_name, ref_id, team_uid=team_uid)

            self._submit_session(user_name, session_id, question, team_uid=team_uid)
            status = self._poll_until_terminal(session_id, user_name)

            if status == "COMPLETED":
                state = self._get_session_state(session_id, user_name)
                text = self._format_answer(state, session_id)
                _reply(text)
            else:
                _reply(
                    f":x: Session ended with status: *{status}*\n"
                    f"_Session ID: `{session_id}`_",
                )

        except requests.HTTPError as e:
            status_code = e.response.status_code if e.response is not None else "?"
            body = self._extract_error_body(e)
            logger.error("Session HTTP error: %s %s", status_code, body, exc_info=True)
            _reply(":x: Session request failed. Please try again later.")
        except requests.Timeout:
            _reply(":hourglass: MAS request timed out. The session may still be running.")
        except TimeoutError:
            _reply(":x: Session timed out. It may still be running.")
        except Exception as e:
            logger.error("Session execution failed: %s", e, exc_info=True)
            _reply(":x: An unexpected error occurred. Please try again later.")

    # ── MAS API calls ─────────────────────────────────────────────

    def _create_session(self, user_name: str, workflow_id: str, *, team_uid: Optional[str] = None) -> str:
        payload = {"blueprintId": workflow_id}
        if team_uid:
            payload["teamId"] = team_uid
        else:
            payload["userId"] = user_name
            payload["identityType"] = "user"

        resp = mas_post(
            f"{self._url}/api/sessions/user.session.create",
            user_name,
            payload,
            timeout=15,
        )
        resp.raise_for_status()
        payload = resp.json()
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            sid = (
                payload.get("sessionId")
                or payload.get("session_id")
                or payload.get("id")
            )
            if sid:
                return str(sid)
        raise ValueError(f"Unexpected create_session response type: {type(payload).__name__}")

    def _submit_session(self, user_name: str, session_id: str, prompt: str, *, team_uid: Optional[str] = None) -> None:
        payload = {
            "sessionId": session_id,
            "inputs": {"user_prompt": prompt},
        }
        if team_uid:
            payload["teamId"] = team_uid
        else:
            payload["userId"] = user_name
            payload["identityType"] = "user"

        resp = mas_post(
            f"{self._url}/api/sessions/user.session.submit",
            user_name,
            payload,
            timeout=15,
        )
        resp.raise_for_status()

    def _get_session_state(self, session_id: str, user_name: str) -> dict:
        resp = mas_get(
            f"{self._url}/api/sessions/session.state.get",
            user_name,
            params={"sessionId": session_id},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()

    # ── Poll / format / post ──────────────────────────────────────

    def _poll_until_terminal(self, session_id: str, user_name: str) -> str:
        elapsed = 0
        while elapsed < _POLL_TIMEOUT:
            time.sleep(_POLL_INTERVAL)
            elapsed += _POLL_INTERVAL

            resp = mas_get(
                f"{self._url}/api/sessions/session.status.get",
                user_name,
                params={"sessionId": session_id},
                timeout=10,
            )
            resp.raise_for_status()
            status = resp.json()
            if isinstance(status, dict):
                status = status.get("status")
            if isinstance(status, str) and status.upper() in _TERMINAL_STATUSES:
                return status.upper()

        raise TimeoutError(
            f"Session {session_id} did not complete within {_POLL_TIMEOUT}s"
        )

    @staticmethod
    def _format_answer(result: dict, session_id: str) -> str:
        answer = (
            result.get("final_answer")
            or result.get("output")
            or result.get("answer")
            or result.get("result")
        )

        if not answer and isinstance(result, dict):
            messages = result.get("messages", [])
            if messages and isinstance(messages, list):
                last = messages[-1]
                if isinstance(last, dict):
                    answer = last.get("content") or last.get("text") or str(last)
                else:
                    answer = str(last)

        if not answer:
            answer = (
                "Session completed but no answer could be extracted.\n"
                "Use `/unifai history <session_id>` to inspect the conversation."
            )

        return (
            f":white_check_mark: *Session Complete*\n\n"
            f"{answer}\n\n"
            f"_Session ID: `{session_id}`_"
        )

    @staticmethod
    def _extract_error_body(error: requests.HTTPError) -> str:
        try:
            if error.response is not None:
                return error.response.json().get("error", "")
        except Exception:
            pass
        return ""

    @staticmethod
    def _post_to_slack(response_url: str, text: str, *, public: bool = False) -> None:
        try:
            parsed = urlparse(response_url or "")
            host = (parsed.hostname or "").lower()
            if parsed.scheme != "https" or not host.endswith(".slack.com"):
                logger.error("Refusing to post to non-Slack response_url: %s", host)
                return

            resp = requests.post(
                response_url,
                json={
                    "response_type": "in_channel" if public else "ephemeral",
                    "text": text,
                },
                timeout=10,
            )
            resp.raise_for_status()
        except Exception as e:
            logger.error("Failed to post deferred response to Slack: %s", e)
