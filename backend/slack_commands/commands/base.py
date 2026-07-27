"""Abstract base for slash command handlers."""
from abc import ABC, abstractmethod

from slack_commands.models import SlackCommand, SlackResponse


class CommandHandler(ABC):
    """
    Base class for slash command handlers.

    Each handler processes one subcommand (e.g. "list", "help", "health")
    and returns a SlackResponse.
    """

    @abstractmethod
    def handle(self, command: SlackCommand) -> SlackResponse:
        """Execute the command and return a Slack-formatted response."""
        ...
