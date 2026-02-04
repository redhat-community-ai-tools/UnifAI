"""Slack validator factory."""
from typing import List

from core.validation.domain.port import DataSourceValidator
from .channel_bot_installation_validator import ChannelBotInstallationValidator


class SlackValidators:
    """Constructs the Slack validators pipeline."""

    def __init__(self, channel_bot_validator: ChannelBotInstallationValidator) -> None:
        self._channel_bot_validator = channel_bot_validator

    def create_validators(self) -> List[DataSourceValidator]:
        return [self._channel_bot_validator]
