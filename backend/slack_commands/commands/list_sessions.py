"""List sessions command — shows the user's sessions from multi-agent."""
import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.formatters import format_session_list
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse

_PAGE_SIZE = 10


class ListSessionsCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        page = self._parse_page(command.args)

        try:
            resp = mas_get(
                f"{self._url}/api/sessions/session.user.list",
                command.user_name,
                params={"userId": command.user_name, "identityType": "user"},
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            sessions = data.get("sessions", data) if isinstance(data, dict) else data
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, operation="Session listing"),
            ) from e

        return format_session_list(sessions, page=page, page_size=_PAGE_SIZE)

    @staticmethod
    def _parse_page(args: str) -> int:
        stripped = args.strip()
        if stripped.isdigit():
            return max(1, int(stripped))
        return 1
