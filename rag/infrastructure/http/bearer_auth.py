"""Caller authentication by bearer token alone, for read-only searches by services.

A service that holds the user's own token (an MCP gateway acting for a signed-in user, an evaluation job)
has no session cookie and must not hold the stack's internal secret, which lets its holder act as any user.
This module authenticates the caller from ``Authorization: Bearer <token>`` and nothing else:

- a Keycloak JWT is verified against the issuer's JWKS (signature, ``iss``, ``exp``) and must name the
  expected audience; the user is ``preferred_username`` and the groups are the ``groups`` claim;
- any other token (an OpenShift console token is opaque) is checked with the Kubernetes TokenReview API,
  only when ``rag_tokenreview_enabled`` is set; the user is ``status.user.username`` and the groups are
  ``status.user.groups``. Service accounts and other ``system:`` identities are refused: a search acts for a
  person.

No session is read or created, no cookie is set, and no header other than ``Authorization`` is trusted.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

import jwt
import requests
from flask import g, jsonify, request

from config.app_config import AppConfig
from infrastructure.http.caller_groups import _groups, _jwks_client, _unverified_claims

logger = logging.getLogger(__name__)

_SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
_ALGORITHMS = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]


@dataclass(frozen=True)
class BearerCaller:
    username: str
    groups: list[str]


def _looks_like_jwt(token: str) -> bool:
    return token.count(".") == 2


def _verify_keycloak(token: str, issuer: str, verify_tls: bool, audience: str) -> BearerCaller | None:
    try:
        key = _jwks_client(issuer, verify_tls).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token, key.key, algorithms=_ALGORITHMS, issuer=issuer.rstrip("/"),
            audience=audience or None,
            options={"verify_aud": bool(audience), "require": ["exp", "iss"]},
        )
    except (jwt.PyJWTError, requests.RequestException, KeyError, ValueError) as e:
        logger.warning(f"Bearer token rejected: {e}")
        return None
    username = claims.get("preferred_username")
    if not username:
        logger.warning("Bearer token has no preferred_username")
        return None
    return BearerCaller(str(username), _groups(claims))


def _token_review(token: str) -> BearerCaller | None:
    """The person behind an opaque (OpenShift) token, from the Kubernetes TokenReview API."""
    try:
        with open(os.path.join(_SA_DIR, "token"), encoding="utf-8") as f:
            sa_token = f.read().strip()
        resp = requests.post(
            "https://kubernetes.default.svc/apis/authentication.k8s.io/v1/tokenreviews",
            json={"apiVersion": "authentication.k8s.io/v1", "kind": "TokenReview", "spec": {"token": token}},
            headers={"Authorization": f"Bearer {sa_token}"},
            verify=os.path.join(_SA_DIR, "ca.crt"),
            timeout=10,
        )
        resp.raise_for_status()
        status = resp.json().get("status", {})
    except (OSError, requests.RequestException, ValueError) as e:
        logger.warning(f"TokenReview failed: {e}")
        return None
    user = status.get("user") or {}
    username = user.get("username")
    if not status.get("authenticated") or not username or str(username).startswith("system:"):
        return None
    groups = [str(x).lstrip("/") for x in user.get("groups") or [] if str(x).strip() and not str(x).startswith("system:")]
    return BearerCaller(str(username), sorted(set(groups)))


def authenticate_bearer(token: str, cfg: Any) -> BearerCaller | None:
    """The caller behind a bearer token, or None when it cannot be trusted."""
    issuer = getattr(cfg, "oidc_issuer_url", "")
    if _looks_like_jwt(token):
        claims = _unverified_claims(token)
        if issuer and str(claims.get("iss", "")).rstrip("/") == issuer.rstrip("/"):
            return _verify_keycloak(token, issuer, getattr(cfg, "oidc_verify_tls", True),
                                    getattr(cfg, "rag_bearer_audience", ""))
    if getattr(cfg, "rag_tokenreview_enabled", False):
        return _token_review(token)
    return None


def rag_require_bearer(f):
    """Endpoint decorator: authenticate by ``Authorization: Bearer`` only; sets ``g.user_id`` and ``g.bearer_groups``."""

    def wrapped(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.lower().startswith("bearer "):
            return jsonify({"error": "bearer token required"}), 401
        caller = authenticate_bearer(auth.split(" ", 1)[1].strip(), AppConfig.get_instance())
        if caller is None:
            return jsonify({"error": "invalid bearer token"}), 401
        g.user_id = caller.username
        g.bearer_groups = caller.groups
        return f(*args, **kwargs)

    wrapped.__name__ = f.__name__
    return wrapped
