"""
SSRF guardrails for OAuth authorization/token endpoints stored in ClientConfig.

Default policy (production-safe):
  - https required
  - reject private / loopback / link-local / reserved IP literals

Local development:
  - http://localhost, http://127.0.0.1, http://[::1], *.localhost always allowed
  - set ALLOW_INSECURE_OAUTH_ENDPOINTS=1 to also allow http and private-IP
    endpoints (e.g. http://keycloak:8080 or https://10.x in a lab)
"""

from __future__ import annotations

import ipaddress
import os
from urllib.parse import urlparse

_TRUTHY = frozenset({"1", "true", "yes", "on"})
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})


def insecure_oauth_endpoints_allowed() -> bool:
    return os.environ.get("ALLOW_INSECURE_OAUTH_ENDPOINTS", "").strip().lower() in _TRUTHY


def _is_local_hostname(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    if not h:
        return False
    if h in _LOCAL_HOSTS or h.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(h).is_loopback
    except ValueError:
        return False


def _is_non_public_ip_literal(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def validate_oauth_endpoint(url: str, *, field_name: str = "endpoint") -> str:
    """Return a normalized endpoint URL or raise ValueError."""
    if url is None:
        return ""
    cleaned = str(url).strip()
    if not cleaned:
        return ""

    parsed = urlparse(cleaned)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"{field_name} must be an http(s) URL")
    if not parsed.hostname:
        raise ValueError(f"{field_name} must include a hostname")

    host = parsed.hostname
    local = _is_local_hostname(host)
    insecure = insecure_oauth_endpoints_allowed()

    if parsed.scheme == "http" and not local and not insecure:
        raise ValueError(
            f"{field_name} must use https "
            "(http is allowed for localhost or when "
            "ALLOW_INSECURE_OAUTH_ENDPOINTS is set)"
        )

    if not local and not insecure and _is_non_public_ip_literal(host):
        raise ValueError(
            f"{field_name} must not target a private/reserved IP "
            "(set ALLOW_INSECURE_OAUTH_ENDPOINTS for local/lab IdPs)"
        )

    return cleaned
