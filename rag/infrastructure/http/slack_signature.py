"""Slack request signature verification (Events API)."""
import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)

MAX_SKEW_SECONDS = 300


def verify_slack_signature(
    signing_secret: str,
    body: bytes,
    timestamp: str,
    signature: str,
    now: float | None = None,
) -> bool:
    """Return True when ``signature`` matches the HMAC of the request body.

    Fails closed: an empty secret, a stale timestamp or a malformed header
    all reject the request.
    """
    if not signing_secret:
        logger.error("Slack signing secret is not configured; rejecting event")
        return False
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    if abs((now if now is not None else time.time()) - ts) > MAX_SKEW_SECONDS:
        logger.warning("Slack request timestamp outside the allowed window")
        return False
    base = b"v0:" + timestamp.encode() + b":" + body
    expected = "v0=" + hmac.new(signing_secret.encode(), base, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature or ""):
        logger.warning("Slack request signature mismatch")
        return False
    return True
