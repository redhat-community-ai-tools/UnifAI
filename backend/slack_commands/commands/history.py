"""History command — shows the conversation messages for a session."""
from typing import List

import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.formatters import ROLE_EMOJI
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse, sanitize_slack_arg

_MAX_MESSAGES = 10
_MAX_CONTENT_LENGTH = 300


class HistoryCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai history <session_id>`"
            )

        try:
            resp = mas_get(
                f"{self._url}/api/sessions/session.chat.get",
                command.user_name,
                params={"sessionId": session_id},
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            chat = resp.json()
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, session_id=session_id, operation="History fetch"),
            ) from e

        messages = chat.get("messages", []) if isinstance(chat, dict) else []
        if not messages:
            return SlackResponse(
                text=f":inbox_tray: No messages yet in session `{session_id}`."
            )

        return self._format_messages(session_id, messages)

    def _format_messages(self, session_id: str, messages: List[dict]) -> SlackResponse:
        total = len(messages)
        shown = messages[-_MAX_MESSAGES:]
        skipped = total - len(shown)

        lines = [f"*Chat History* — `{session_id}`\n"]

        if skipped > 0:
            lines.append(f"_({skipped} earlier messages not shown)_\n")

        for msg in shown:
            if not isinstance(msg, dict):
                continue
            role = str(msg.get("role") or msg.get("type") or "unknown")
            content = msg.get("content") or msg.get("text") or ""
            emoji = ROLE_EMOJI.get(role.lower(), ":speech_balloon:")

            if isinstance(content, list):
                content = " ".join(
                    part.get("text", "")
                    for part in content
                    if isinstance(part, dict)
                )

            content = str(content)
            if len(content) > _MAX_CONTENT_LENGTH:
                content = content[:_MAX_CONTENT_LENGTH] + "…"

            lines.append(f"{emoji} *{role}:* {content}")

        return SlackResponse(text="\n".join(lines))
