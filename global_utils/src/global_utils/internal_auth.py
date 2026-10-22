"""Trust marker for service-to-service calls.

``X-Authenticated-User`` is only honoured when the request also carries the
shared secret (``INTERNAL_AUTH_SECRET``) in ``X-Internal-Auth``, or when the
explicit development mode (``UNIFAI_DEV_MODE=true``) is on.  The secret is
compared in constant time.  Every service that sends or accepts the header
must be configured with the same secret.

The secret is only ever sent to the stack's own services: a caller whose URL comes from
a configuration users can edit (retriever ``api_url``, RAG provider ``base_url``) passes
that URL, and gets no header at all when its host is not a trusted service host.
"""
import hmac
import os
from typing import Mapping, Optional
from urllib.parse import urlsplit

from global_utils.constants import INTERNAL_AUTH_HEADER, INTERNAL_SECRET_HEADER

ENV_SECRET = "INTERNAL_AUTH_SECRET"
ENV_DEV_MODE = "UNIFAI_DEV_MODE"
ENV_TRUSTED_HOSTS = "INTERNAL_AUTH_HOSTS"
"""Comma-separated extra host names (exact match) allowed to receive the secret."""

SERVICE_HOSTS = frozenset({
    "unifai-rag-server", "unifai-multiagent-be", "unifai-backend", "unifai-identity", "identity",
})
"""Kubernetes Service names of the stack, trusted bare or as ``<name>.<POD_NAMESPACE>.svc[.cluster.local]``."""

_TRUTHY = {"1", "true", "yes", "on"}


def dev_mode_enabled() -> bool:
    """True only when ``UNIFAI_DEV_MODE`` is explicitly set to a truthy value."""
    return os.getenv(ENV_DEV_MODE, "").strip().lower() in _TRUTHY


def internal_secret() -> str:
    return os.getenv(ENV_SECRET, "").strip()


def is_trusted_target(url: str) -> bool:
    """True when ``url`` points to one of the stack's services (exact host match after parsing).

    Rejects user info (``http://unifai-rag-server@evil``), look-alike suffixes
    (``unifai-rag-server.evil.com``), other namespaces and non-HTTP schemes.
    """
    try:
        parts = urlsplit(str(url).strip())
        host = (parts.hostname or "").lower().rstrip(".")
        _ = parts.port  # raises on a malformed port
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not host or parts.username is not None or "@" in parts.netloc:
        return False
    extra = {h.strip().lower() for h in os.getenv(ENV_TRUSTED_HOSTS, "").split(",") if h.strip()}
    if host in extra:
        return True
    name, _, rest = host.partition(".")
    if name not in SERVICE_HOSTS:
        return False
    if not rest:
        return True
    ns = os.getenv("POD_NAMESPACE", "").strip().lower()
    return bool(ns) and rest in (f"{ns}.svc", f"{ns}.svc.cluster.local")


def internal_auth_headers(user: Optional[str] = None, url: Optional[str] = None) -> dict:
    """Headers an internal caller adds to outbound service-to-service requests.

    With ``url`` (mandatory when it comes from user-editable configuration), nothing is
    returned unless the URL targets a trusted service host (``is_trusted_target``).
    """
    if url is not None and not is_trusted_target(url):
        return {}
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
