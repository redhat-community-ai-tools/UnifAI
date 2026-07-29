"""List workflows command — shows available workflows from multi-agent."""
import re

import requests

from global_utils.identity_client import IdentityClient
from slack_commands.commands.base import CommandHandler
from slack_commands.http import MAS_TIMEOUT, handle_client_error, mas_get
from slack_commands.formatters import format_workflow_list
from slack_commands.models import MASRequestError, SlackCommand, SlackResponse

_TEAM_FLAG = re.compile(r"--team\s+(\S+)", re.IGNORECASE)

_HELP_FLAG = re.compile(r"(^|\s)--help\b", re.IGNORECASE)

_USAGE = (
    "*Usage:* `/unifai workflows [--team <team_uid>]`\n\n"
    "*Options:*\n"
    "• `--team <team_uid>` — List workflows owned by a team\n\n"
    "_Without `--team`, lists your personal workflows._\n"
    "_Run `/unifai teams` to see your team UIDs._"
)


class ListWorkflowsCommand(CommandHandler):

    def __init__(self, base_url: str, identity_client: IdentityClient):
        self._url = base_url.rstrip("/")
        self._identity = identity_client

    def handle(self, command: SlackCommand) -> SlackResponse:
        if _HELP_FLAG.search(command.args):
            return SlackResponse(text=_USAGE)

        team_match = _TEAM_FLAG.search(command.args)

        if team_match:
            team_uid = team_match.group(1)
            if not self._identity.is_member(command.user_name, team_uid):
                return SlackResponse(
                    text=f":x: Team `{team_uid}` not found or you are not a member.",
                )
            params = {"teamId": team_uid}
            label = f"team `{team_uid}`"
        else:
            params = {"userId": command.user_name, "identityType": "user"}
            label = None

        try:
            resp = mas_get(
                f"{self._url}/api/blueprints/available.blueprints.summary.get",
                command.user_name,
                params=params,
                timeout=MAS_TIMEOUT,
            )
            resp.raise_for_status()
            workflows = resp.json()
        except requests.RequestException as e:
            raise MASRequestError(
                handle_client_error(e, operation="Workflow listing"),
            ) from e

        return format_workflow_list(workflows, label=label)
