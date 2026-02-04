"""Channel Bot Installation Validator."""
from typing import Optional, Any, Tuple, Protocol

from core.validation.domain.port import DataSourceValidator
from core.validation.domain.model import ValidationIssue
from shared.logger import logger


class BotInstallationCheckerPort(Protocol):
    """Port for bot installation checking - implementations injected at runtime."""
    def is_bot_installed_in_channel(self, channel_id: str) -> bool:
        ...


class MembershipUpdaterPort(Protocol):
    """Port for updating membership status - implementations injected at runtime."""
    def update_membership(self, channel_id: str, is_member: bool) -> bool:
        ...


class ChannelBotInstallationValidator(DataSourceValidator):
    """Validates that the Slack app (bot user) is a member of the provided channel."""
    
    name = "ChannelBotInstallationValidator"
    error_message = "Invite the TAG-001 app user to this channel to enable embedding. Channel: {channel_name}"
    error_message_key = "Channel bot not installed"

    def __init__(
        self,
        bot_checker: BotInstallationCheckerPort,
        membership_updater: MembershipUpdaterPort,
    ) -> None:
        self._bot_checker = bot_checker
        self._membership_updater = membership_updater

    def validate(self, **kwargs: Any) -> Tuple[bool, Optional[ValidationIssue]]:
        """
        Validate that the Slack app (bot user) is a member of the provided channel.
        Falls back to Slack API if cache is missing/unknown.
        Expected kwargs:
          - channel_id: str (required)
          - channel_name: str (optional, for nicer messaging)
        """
        channel_id = kwargs.get("channel_id")
        channel_name = kwargs.get("channel_name") or ""

        if not isinstance(channel_id, str) or not channel_id:
            # Without a channel_id we cannot validate; do not block
            return True, None

        try:
            # Always check with Slack API via the checker, regardless of cached is_app_member
            is_member = self._bot_checker.is_bot_installed_in_channel(channel_id)
            # cache result for follow-up update without re-calling the checker
            self._membership_updater.update_membership(channel_id, is_member)
            
            if not is_member:
                return False, self.build_issue(
                    self.error_message.format(channel_name=channel_name or channel_id)
                )

            return True, None
        except Exception as e:
            logger.error(f"ChannelBotInstallationValidator: unexpected error validating {channel_id}: {e}")
            return True, None
