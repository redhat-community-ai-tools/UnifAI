"""List workflows command — shows available workflows from multi-agent."""
import requests

from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.formatters import format_workflow_list
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse


class ListWorkflowsCommand(CommandHandler):

    def __init__(self, base_url: str):
        self._url = base_url.rstrip("/")

    def handle(self, command: SlackCommand) -> SlackResponse:
        try:
            resp = mas_get(
                f"{self._url}/api/blueprints/available.blueprints.summary.get",
                command.user_name,
                params={"userId": command.user_name, "identityType": "user"},
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            workflows = resp.json()
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, operation="Workflow listing"),
            ) from e

        return format_workflow_list(workflows)
