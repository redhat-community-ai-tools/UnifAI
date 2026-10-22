"""Best-effort server-side fetch of a routing explanation for a response.

The browser cannot reach model gateways that live on a private network or
require the user's token, so the backend fetches ``metadata_lookup_url`` itself
(identity headers relayed through an optional forwarder) and attaches the JSON
body to the response metadata.  Every failure is swallowed: this must never
block or break an LLM call, and the token never leaves the backend.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_LOOKUP_TIMEOUT_S = 2.0


def resolve_lookup_url(
    url_template: Optional[str],
    response_id: Optional[str],
    request_id: Optional[str] = None,
) -> Optional[str]:
    """Fill ``{response_id}`` / ``{request_id}`` in *url_template*.

    Returns ``None`` when there is no template or when a placeholder used by
    the template has no value to substitute.
    """
    if not url_template:
        return None
    for placeholder, value in (("{response_id}", response_id), ("{request_id}", request_id)):
        if placeholder in url_template and not value:
            return None
    return (
        url_template
        .replace("{response_id}", response_id or "")
        .replace("{request_id}", request_id or "")
    )


def fetch_routing(
    url_template: Optional[str],
    response_id: Optional[str],
    forwarder: Any,
    timeout_s: float = DEFAULT_LOOKUP_TIMEOUT_S,
    transport: Optional[httpx.BaseTransport] = None,
    request_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Return the JSON object served at the resolved lookup URL, or ``None``.

    The template may use ``{response_id}`` (the completion id) and/or
    ``{request_id}`` (the id this client sent with the call).  ``forwarder`` must expose ``headers(templates, forward_token)`` (the
    ``IdentityForwarder`` contract).  Without a forwarder, or when it cannot
    produce an ``Authorization`` header, nothing is fetched.
    """
    url = resolve_lookup_url(url_template, response_id, request_id)
    if not url or forwarder is None:
        return None
    try:
        headers = forwarder.headers({}, True)
        if not headers or "Authorization" not in headers:
            return None
        with httpx.Client(timeout=timeout_s, transport=transport) as client:
            resp = client.get(url, headers=headers)
        if resp.status_code != 200:
            logger.debug("metadata lookup returned HTTP %s", resp.status_code)
            return None
        body = resp.json()
        return body if isinstance(body, dict) else None
    except Exception as exc:  # best-effort by design; never raise to the caller
        logger.debug("metadata lookup failed: %s", type(exc).__name__)
        return None
