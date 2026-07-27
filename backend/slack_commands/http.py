"""HTTP helpers for outbound MAS requests."""
import logging

import requests

from global_utils.constants import INTERNAL_AUTH_HEADER
from slack_commands.models import SlackResponse

logger = logging.getLogger(__name__)

_AUTH_HEADER = INTERNAL_AUTH_HEADER

MAS_TIMEOUT = 10


def mas_get(
    url: str, user_id: str, params: dict = None, **kwargs,
) -> requests.Response:
    """GET from MAS with user identity header."""
    return requests.get(
        url, params=params, headers={_AUTH_HEADER: user_id}, **kwargs,
    )


def mas_post(
    url: str, user_id: str, payload: dict, **kwargs,
) -> requests.Response:
    """POST JSON to MAS with user identity header."""
    headers = {_AUTH_HEADER: user_id, "Content-Type": "application/json"}
    return requests.post(url, json=payload, headers=headers, **kwargs)


def mas_delete(
    url: str, user_id: str, params: dict = None, **kwargs,
) -> requests.Response:
    """DELETE from MAS with user identity header."""
    return requests.delete(
        url, params=params, headers={_AUTH_HEADER: user_id}, **kwargs,
    )


def handle_client_error(
    error: Exception,
    *,
    session_id: str = "",
    operation: str = "Request",
) -> SlackResponse:
    """Map MAS HTTP exceptions to user-friendly Slack responses."""
    if isinstance(error, requests.HTTPError):
        if error.response is not None and error.response.status_code == 404:
            return SlackResponse(
                text=f":x: Session `{session_id}` not found."
                if session_id
                else ":x: Resource not found.",
            )
        logger.error("%s failed: %s", operation, error, exc_info=True)
        return SlackResponse(
            text=f":x: {operation} failed. Please try again later.",
        )
    if isinstance(error, requests.Timeout):
        logger.warning("%s timed out (session=%s)", operation, session_id or "n/a")
        return SlackResponse(text=":hourglass: Multi-agent service timed out.")
    logger.error("%s failed: %s", operation, error, exc_info=True)
    return SlackResponse(
        text=":x: An unexpected error occurred. Please try again later.",
    )
