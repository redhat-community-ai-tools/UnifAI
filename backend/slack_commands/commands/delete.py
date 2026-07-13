"""Delete command — permanently removes a session."""
import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_delete
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse, sanitize_slack_arg


class DeleteCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        session_id = sanitize_slack_arg(command.args)

        if not session_id:
            return SlackResponse(
                text="*Usage:* `/unifai delete <session_id>`"
            )

        try:
            resp = mas_delete(
                f"{self._url}/api/sessions/session.delete",
                command.user_name,
                params={"sessionId": session_id},
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            deleted = resp.json().get("success", False)
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, session_id=session_id, operation="Delete"),
            ) from e

        if deleted:
            return SlackResponse(
                text=f":wastebasket: Session `{session_id}` has been deleted.",
                response_type="in_channel",
            )

        return SlackResponse(
            text=f":warning: Session `{session_id}` was not found or already deleted."
        )
