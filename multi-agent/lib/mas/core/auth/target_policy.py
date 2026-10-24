"""Where may a credential be presented?

A stored OAuth credential is issued by an authorization server (its
``server_identifier``) and is valid for every resource server of that issuer.
The URL a resource points at, however, is user-editable. Without a check, a
resource that names a real issuer but points at another host would receive the
user's token. Two rules close that:

* A stored credential carries the origins of the resource URLs the user signed
  in for (``resource_origins``). It is presented only to one of them. A
  credential without recorded origins (stored before this rule, or typed in by
  the user) is presented only to the origin of its own ``server_identifier``,
  which for an API key *is* the server URL.
* The acting user's own platform token (``forward_user_token``) is sent only to
  cluster-internal services or to hosts the operator lists in
  ``FORWARD_TOKEN_ALLOWED_HOSTS``.
"""
from __future__ import annotations

import os
from collections.abc import Iterable
from urllib.parse import urlparse

ALLOWED_HOSTS_ENV = "FORWARD_TOKEN_ALLOWED_HOSTS"


def origin_of(url: str) -> str:
    """``scheme://host[:port]`` of an http(s) URL, lower-cased, or ``""``."""
    try:
        parts = urlparse((url or "").strip())
        host = (parts.hostname or "").lower()
        if parts.scheme not in ("http", "https") or not host or parts.username or parts.password:
            return ""
        port = f":{parts.port}" if parts.port else ""
        host = f"[{host}]" if ":" in host else host
        return f"{parts.scheme}://{host}{port}"
    except ValueError:
        return ""


def credential_may_be_sent(server_identifier: str, resource_origins: Iterable[str], target_url: str) -> bool:
    """May a credential of ``server_identifier`` be presented to ``target_url``?"""
    target = origin_of(target_url)
    if not target:
        return False
    recorded = {o for o in (origin_of(o) or o for o in resource_origins or []) if o}
    if recorded:
        return target in recorded
    return target == origin_of(server_identifier)


def _is_cluster_internal(host: str) -> bool:
    return (
        host.endswith(".svc")
        or host.endswith(".svc.cluster.local")
        or ("." not in host and host != "localhost")  # a bare service name of the same namespace
    )


def forwarding_target_allowed(target_url: str, allowed_hosts: Iterable[str] | None = None) -> bool:
    """May the acting user's own platform token be sent to ``target_url``?"""
    origin = origin_of(target_url)
    if not origin:
        return False
    host = urlparse(origin).hostname or ""
    if _is_cluster_internal(host):
        return True
    if allowed_hosts is None:
        allowed_hosts = os.environ.get(ALLOWED_HOSTS_ENV, "").split(",")
    return host in {h.strip().lower() for h in allowed_hosts if h and h.strip()}
