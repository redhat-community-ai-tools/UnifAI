"""Help command — lists available commands."""
from slack_commands.commands.base import CommandHandler
from slack_commands.models import SlackCommand, SlackResponse


class HelpCommand(CommandHandler):

    def handle(self, command: SlackCommand) -> SlackResponse:
        return SlackResponse(
            text=(
                "*Available Commands*\n\n"
                "*Sessions*\n"
                "• `/unifai ask <workflow> <question>` — Start a new session\n"
                "• `/unifai ask <session_id> <question>` — Continue an existing session\n"
                "• `/unifai list [page]` — List your sessions\n"
                "• `/unifai status <session_id>` — Check session status\n"
                "• `/unifai history <session_id>` — View session chat history\n"
                "• `/unifai cancel <session_id>` — Cancel a running session\n"
                "• `/unifai delete <session_id>` — Permanently delete a session\n\n"
                "*Discovery*\n"
                "• `/unifai workflows` — List available workflows\n\n"
                "*Utility*\n"
                "• `/unifai help` — Show this message\n"
                "• `/unifai health` — Check service status\n"
                "• `/unifai whoami` — Show your Slack identity info\n\n"
                "*Tip:* Add `--public` to any command to share the response with the channel.\n"
            ),
        )
