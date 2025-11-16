from typing import List
from common.interfaces import DataSourceValidator
from .channel_bot_installation_validator import ChannelBotInstallationValidator


class SlackValidators:
	"""
	Constructs the Slack validators pipeline.
	"""
	def create_validators(self) -> List[DataSourceValidator]:
		return [
			ChannelBotInstallationValidator(),
		]


