"""Infrastructure adapters for Slack bot installation checking.

These adapters implement the BotInstallationCheckerPort and MembershipUpdaterPort
using Slack API and MongoDB storage respectively.
"""
import time
from typing import Any

from shared.logger import logger


class BotInstallationCheckerAdapter:
    """
    Slack API-based bot installation checker.
    
    Checks if the bot is a member of a channel using the Slack conversations.info API.
    """

    def __init__(self, slack_connector: Any) -> None:
        self._connector = slack_connector

    def is_bot_installed_in_channel(self, channel_id: str) -> bool:
        """Check if bot is member of channel via Slack API."""
        if not isinstance(channel_id, str) or not channel_id:
            return False

        if self._connector is not None:
            try:
                resp = self._connector._make_api_request("conversations.info", {"channel": channel_id})
                if resp.get("ok"):
                    channel = (resp.get("channel") or {})
                    is_member = bool(channel.get("is_member"))
                    return is_member
                else:
                    logger.warning(f"BotInstallationCheckerAdapter: Slack API error for {channel_id}: {resp.get('error')}")
            except Exception as e:
                logger.warning(f"BotInstallationCheckerAdapter: conversations.info failed for {channel_id}: {e}")
        else:
            logger.warning("BotInstallationCheckerAdapter: no configured connector; skipping API check")

        return False


class MembershipUpdaterAdapter:
    """
    MongoDB-based membership status updater.
    
    Updates the bot membership flag in the slack_channels collection.
    """

    def __init__(self, storage: Any) -> None:
        self._storage = storage

    def update_membership(self, channel_id: str, is_member: bool) -> bool:
        """Update bot membership flag in database."""
        try:
            if hasattr(self._storage, "slack_channels") and hasattr(self._storage.slack_channels, "update_membership"):
                return bool(
                    self._storage.slack_channels.update_membership(
                        channel_id=channel_id,
                        is_member=is_member,
                        timestamp=time.time()
                    )
                )
            return False
        except Exception as e:
            logger.warning(f"MembershipUpdaterAdapter: failed to update membership for {channel_id}: {e}")
            return False
