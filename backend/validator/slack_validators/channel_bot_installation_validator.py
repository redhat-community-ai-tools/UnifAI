from typing import Optional, Any, Tuple
import time
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from services.slack.channel_bot_installation_checker import ChannelBotInstallationChecker
from common.interfaces import DataSourceValidator, ValidationIssue
from shared.logger import logger


class ChannelBotInstallationValidator(DataSourceValidator):
	name = "ChannelBotInstallationValidator"
	error_message = "Invite the TAG-001 app user to this channel to enable embedding. Channel: {channel_name}"
	error_message_key = "Channel bot not installed"

	def __init__(self) -> None:
		self._checker = ChannelBotInstallationChecker()

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
			is_member = self._checker.is_bot_installed_in_channel(channel_id)
			# cache result for follow-up update without re-calling the checker
			self.update_bot_membership(channel_id, is_member)
			if not is_member:
				return False, self.build_issue(
					self.error_message.format(channel_name=channel_name or channel_id)
				)

			return True, None
		except Exception as e:
			logger.error(f"SlackAppInstalledValidator: unexpected error validating {channel_id}: {e}")
			return True, None

	def update_bot_membership(self, channel_id: str, is_member: bool) -> bool:
		"""
		Update the bot membership flag in the channels repository using the most recent
		validation result (if available). Falls back to checking once if no cached value exists.
		"""
		try:
			return bool(get_mongo_storage().slack_channels.update_membership(channel_id=channel_id, is_member=is_member, timestamp=time.time()))
		except Exception as e:
			logger.warning(f"ChannelBotInstallationValidator: failed to update membership for {channel_id}: {e}")
			return False


