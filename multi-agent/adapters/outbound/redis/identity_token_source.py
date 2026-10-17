"""
Redis-backed :class:`IdentityTokenSource`.

Resolves the acting user's access token from the identity service's own
server-session hash (``identity:session:{sid}``), through a binding written at
submission time (``mas:identity_binding:{mas_session_id}``).  Both live in the
same Redis, so the binding adds no new trust boundary, and neither is ever
copied into MongoDB or Temporal history.

When the access token is within ``refresh_skew_seconds`` of expiry it is
refreshed against the Keycloak token endpoint with the session's refresh
token, and written back to the identity hash exactly as the identity service
does, so the UI session and running workflows keep sharing one token.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import requests
from global_utils.redis.constants import identity_session_key
from global_utils.redis.session_model import UserSessionData
from mas.core.identity_forwarding import IdentityTokenSource, IdentityTokenUnavailable

logger = logging.getLogger(__name__)

IDENTITY_BINDING_PREFIX = "mas:identity_binding"


def identity_binding_key(session_id: str) -> str:
    return f"{IDENTITY_BINDING_PREFIX}:{session_id}"


class RedisIdentityTokenSource(IdentityTokenSource):

    def __init__(
        self,
        kv_store: Any,
        token_url: str = "",
        client_id: str = "",
        client_secret: str = "",
        verify_tls: bool = True,
        refresh_skew_seconds: int = 60,
        binding_ttl_seconds: int = 36_000,
        http_post: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._kv = kv_store
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._verify_tls = verify_tls
        self._skew = refresh_skew_seconds
        self._binding_ttl = binding_ttl_seconds
        self._post = http_post or requests.post
        self._now = clock

    # ── binding ──────────────────────────────────────────────────────────

    def bind(self, session_id: str, identity_session_id: str, username: str) -> None:
        if not session_id or not identity_session_id or not username:
            return
        ttl = self._binding_ttl
        data = UserSessionData.from_redis_hash(self._kv.hget(identity_session_key(identity_session_id)))
        if data is not None and data.session_expires_at:
            ttl = max(1, min(ttl, int(float(data.session_expires_at) - self._now())))
        self._kv.hset(
            identity_binding_key(session_id),
            {"identity_session_id": identity_session_id, "username": username},
            ttl_seconds=ttl,
        )

    # ── resolution ───────────────────────────────────────────────────────

    def get_access_token(self, session_id: str, username: str) -> str:
        binding = _decode(self._kv.hget(identity_binding_key(session_id)))
        sid = binding.get("identity_session_id", "")
        if not sid:
            raise IdentityTokenUnavailable(
                f"no identity binding for session {session_id}: it was not submitted by a signed-in user"
            )
        if binding.get("username", "") != username:
            raise IdentityTokenUnavailable(
                f"identity binding for session {session_id} belongs to another user"
            )

        key = identity_session_key(sid)
        raw = _decode(self._kv.hget(key))
        data = UserSessionData.from_redis_hash(raw)
        if data is None or not data.access_token:
            raise IdentityTokenUnavailable("the user's identity session has ended; sign in again")
        if data.is_session_expired():
            raise IdentityTokenUnavailable("the user's identity session has expired; sign in again")

        expires_at = float(data.token_expires_at or 0)
        if expires_at and expires_at - self._now() > self._skew:
            return data.access_token
        if not expires_at and not data.refresh_token:
            return data.access_token
        return self._refresh(key, raw, data)

    def _refresh(self, key: str, raw: dict[str, str], data: UserSessionData) -> str:
        if not (self._token_url and self._client_id and data.refresh_token):
            raise IdentityTokenUnavailable(
                "the user's access token is expiring and token refresh is not configured"
            )
        try:
            resp = self._post(
                self._token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": data.refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                timeout=10,
                verify=self._verify_tls,
            )
            resp.raise_for_status()
            token = resp.json()
        except Exception as exc:
            raise IdentityTokenUnavailable(f"refreshing the user's access token failed: {exc}") from exc

        access = token.get("access_token")
        if not access:
            raise IdentityTokenUnavailable("token endpoint returned no access_token")
        updated = dict(raw)
        updated["access_token"] = access
        if token.get("refresh_token"):
            updated["refresh_token"] = token["refresh_token"]
        updated["token_expires_at"] = str(int(self._now()) + int(token.get("expires_in") or 0))
        ttl = None
        if data.session_expires_at:
            ttl = max(1, int(float(data.session_expires_at) - self._now()))
        self._kv.hset(key, updated, ttl_seconds=ttl)
        logger.info("Refreshed forwarded access token for user %s", data.username)
        return access


def _decode(raw: Any) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in (raw or {}).items():
        key = k.decode("utf-8") if isinstance(k, bytes) else str(k)
        out[key] = v.decode("utf-8") if isinstance(v, bytes) else ("" if v is None else str(v))
    return out
