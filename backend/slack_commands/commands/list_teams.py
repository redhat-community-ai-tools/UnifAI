"""List teams command — shows teams the user belongs to."""
import requests

from global_utils.identity_client import IdentityClient
from slack_commands.commands.base import CommandHandler
from slack_commands.formatters import format_team_list
from slack_commands.models import SlackCommand, SlackResponse


class ListTeamsCommand(CommandHandler):

    def __init__(self, identity_client: IdentityClient):
        self._identity = identity_client

    def handle(self, command: SlackCommand) -> SlackResponse:
        try:
            teams = self._identity.list_teams_for_user(command.user_name)
        except requests.RequestException:
            return SlackResponse(
                text=":x: Failed to fetch teams. Please try again later.",
            )

        return format_team_list(teams)
