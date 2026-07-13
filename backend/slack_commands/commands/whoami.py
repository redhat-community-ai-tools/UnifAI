"""Whoami command — shows the caller's Slack identity info."""
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse


class WhoamiCommand(CommandHandler):

    def handle(self, command: SlackCommand) -> SlackResponse:
        return SlackResponse(
            text=(
                f"*Identity Info*\n"
                f"• user_name: `{command.user_name}`\n"
                f"• user_id: `{command.user_id}`\n"
                f"• channel: `{command.channel_name}` (`{command.channel_id}`)\n"
                f"• team_id: `{command.team_id}`"
            ),
        )
