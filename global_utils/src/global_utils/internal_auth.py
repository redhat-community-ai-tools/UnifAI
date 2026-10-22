"""Trust marker for service-to-service calls.

``X-Authenticated-User`` is only honoured when the request also carries the
shared secret (``INTERNAL_AUTH_SECRET``) in ``X-Internal-Auth``, or when the
explicit development mode (``UNIFAI_DEV_MODE=true``) is on.  The secret is
compared in constant time.  Every service that sends or accepts the header
must be configured with the same secret.
"""
import hmac
import os
from typing import Mapping, Optional

from global_utils.constants import INTERNAL_AUTH_HEADER, INTERNAL_SECRET_HEADER

ENV_SECRET = "INTERNAL_AUTH_SECRET"
ENV_DEV_MODE = "UNIFAI_DEV_MODE"

_TRUTHY = {"1", "true", "yes", "on"}


def dev_mode_enabled() -> bool:
    """True only when ``UNIFAI_DEV_MODE`` is explicitly set to a truthy value."""
    return os.getenv(ENV_DEV_MODE, "").strip().lower() in _TRUTHY


def internal_secret() -> str:
    return os.getenv(ENV_SECRET, "").strip()


def internal_auth_headers(user: Optional[str] = None) -> dict:
    """Headers an internal caller adds to outbound service-to-service requests."""
    headers: dict = {}
    secret = internal_secret()
    if secret:
        headers[INTERNAL_SECRET_HEADER] = secret
    if user:
        headers[INTERNAL_AUTH_HEADER] = user
    return headers


def is_trusted_internal_request(headers: Mapping[str, str]) -> bool:
    """True when the request proves it comes from a trusted internal service."""
    if dev_mode_enabled():
        return True
    secret = internal_secret()
    if not secret:
        return False
    supplied = (headers.get(INTERNAL_SECRET_HEADER) or "").strip()
    return hmac.compare_digest(supplied.encode(), secret.encode())


def trusted_header_user(headers: Mapping[str, str]) -> Optional[str]:
    """The ``X-Authenticated-User`` value, only for trusted internal requests."""
    if not is_trusted_internal_request(headers):
        return None
    user = (headers.get(INTERNAL_AUTH_HEADER) or "").strip()
    return user or None
