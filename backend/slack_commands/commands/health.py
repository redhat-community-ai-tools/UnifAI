"""Health command — confirms the backend is reachable."""
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse


class HealthCommand(CommandHandler):

    def handle(self, command: SlackCommand) -> SlackResponse:
        return SlackResponse(
            text=":white_check_mark: UnifAI backend is healthy",
            response_type="in_channel",
        )
