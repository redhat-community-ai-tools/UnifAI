from typing import Optional, Tuple
from shared.logger import logger
from utils.storage.mongo.mongo_helpers import get_mongo_storage
from providers.slack.slack import _get_configured_connector


class ChannelBotInstallationChecker:
    """
    Determines whether the Slack app (bot) is installed in a given channel.
    """

    def __init__(self) -> None:
        self._repo = get_mongo_storage().slack_channels

    def is_bot_installed_in_channel(self, channel_id: str) -> bool:
        """
        Check if the Slack app (bot) is installed in a given channel.
        
        Returns:
            (is_bot_installed)
            - is_bot_installed: True, False 
        """
        if not isinstance(channel_id, str) or not channel_id:
            return False

        connector = _get_configured_connector()
        if connector is not None:
            try:
                resp = connector._make_api_request("conversations.info", {"channel": channel_id})
                if resp.get("ok"):
                    channel = (resp.get("channel") or {})
                    is_member = bool(channel.get("is_member"))
                    return is_member
                else:
                    logger.warning(f"ChannelBotInstallationChecker: Slack API error for {channel_id}: {resp.get('error')}")
            except Exception as e:
                logger.warning(f"ChannelBotInstallationChecker: conversations.info failed for {channel_id}: {e}")
        else:
            logger.warning("ChannelBotInstallationChecker: no configured connector; skipping API check")

        return False


