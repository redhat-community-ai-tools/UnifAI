"""The caller's groups, which decide the shared sources a search may return.

Two trustworthy origins only:

- a signed-in browser session: the identity service stored the user's OIDC access
  token in the Redis session after login, so its ``groups`` claim is read as is;
- an internal caller (e.g. MAS) forwarding the user's own token as
  ``Authorization: Bearer``: the token is verified against the issuer's JWKS
  (``OIDC_ISSUER_URL``) and must belong to the user the request acts for, or to a
  member of the team workspace it acts for.

Anything else yields no group, so only the caller's own sources are searched.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
import ssl
from functools import lru_cache
from typing import Any

import jwt
import requests
from flask import g, request

logger = logging.getLogger(__name__)


def _groups(claims: dict[str, Any]) -> list[str]:
    raw = claims.get("groups") or []
    if isinstance(raw, str):
        raw = [raw]
    return sorted({str(x).lstrip("/") for x in raw if str(x).strip()})


def _unverified_claims(token: str) -> dict[str, Any]:
    try:
        payload = token.split(".")[1]
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError, binascii.Error):
        return {}
    return claims if isinstance(claims, dict) else {}


@lru_cache(maxsize=4)
def _jwks_client(issuer: str, verify_tls: bool) -> jwt.PyJWKClient:
    config = requests.get(f"{issuer.rstrip('/')}/.well-known/openid-configuration", timeout=10, verify=verify_tls)
    config.raise_for_status()
    ctx = ssl.create_default_context()
    if not verify_tls:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return jwt.PyJWKClient(config.json()["jwks_uri"], cache_keys=True, lifespan=300, ssl_context=ctx)


def verify_bearer(token: str, issuer: str, verify_tls: bool = True) -> dict[str, Any] | None:
    """Claims of a token signed by the issuer and not expired, else None."""
    try:
        key = _jwks_client(issuer, verify_tls).get_signing_key_from_jwt(token)
        return jwt.decode(token, key.key, algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"],
                          issuer=issuer.rstrip("/"), options={"verify_aud": False, "require": ["exp", "iss"]})
    except (jwt.PyJWTError, requests.RequestException, KeyError, ValueError) as e:
        logger.warning(f"Forwarded bearer token rejected: {e}")
        return None


def caller_groups(issuer: str = "", verify_tls: bool = True) -> list[str]:
    """Groups of the current caller, or [] when none can be established."""
    session = getattr(g, "identity_session", None)
    token = getattr(session, "access_token", None)
    if token:
        return _groups(_unverified_claims(token))

    auth = request.headers.get("Authorization", "")
    if not (issuer and auth.lower().startswith("bearer ")):
        return []
    claims = verify_bearer(auth.split(" ", 1)[1].strip(), issuer, verify_tls)
    if not claims:
        return []
    username = claims.get("preferred_username")
    workspace = getattr(g, "user_id", None)
    if username != workspace and not _member_of_workspace(username, workspace):
        logger.warning("Forwarded bearer token belongs to another user than the request; ignoring it")
        return []
    return _groups(claims)


def _member_of_workspace(username: Any, workspace: Any) -> bool:
    """True when the token's person is a member of the team workspace the request acts for.

    In a team workspace the request is made for the team id, while the forwarded token
    is the signed-in person's own: their groups are the right ones as long as they
    belong to that team. Anything unverifiable counts as not a member.
    """
    if not username or not workspace or username == workspace:
        return False
    try:
        from bootstrap.app_container import identity_client

        return bool(identity_client().is_member(str(username), str(workspace)))
    except Exception:  # noqa: BLE001 - membership must never raise into a search
        logger.warning("Team membership check failed; ignoring the forwarded token", exc_info=True)
        return False
