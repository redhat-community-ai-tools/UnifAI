"""Status command — shows current status and metadata for a session."""
import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.formatters import STATUS_EMOJI
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse, sanitize_slack_arg


class StatusCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai status <session_id>`"
            )

        try:
            status_resp = mas_get(
                f"{self._url}/api/sessions/session.status.get",
                command.user_name,
                params={"sessionId": session_id},
                timeout=MAS_TIMEOUT,
            )
            status_resp.raise_for_status()
            status = status_resp.json()
            if isinstance(status, dict):
                status = status.get("status")
            status = status.upper() if isinstance(status, str) else None

            meta_resp = mas_get(
                f"{self._url}/api/sessions/session.meta",
                command.user_name,
                params={"sessionId": session_id},
                timeout=MAS_TIMEOUT,
            )
            meta_resp.raise_for_status()
            meta_data = meta_resp.json()
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, session_id=session_id, operation="Status check"),
            ) from e

        emoji = STATUS_EMOJI.get(str(status or "unknown").upper(), ":grey_question:")
        meta = meta_data.get("meta", {}) if isinstance(meta_data, dict) else {}
        title = meta.get("title") or "untitled"
        status_message = meta.get("status_message") or ""

        lines = [
            f"{emoji} *Session Status*",
            f"• *ID:* `{session_id}`",
            f"• *Status:* {status or 'unknown'}",
            f"• *Title:* {title}",
        ]
        if status_message:
            lines.append(f"• *Message:* {status_message}")

        return SlackResponse(text="\n".join(lines))
