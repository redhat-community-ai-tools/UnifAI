"""
OAuth2Strategy — self-contained OAuth 2.1 auth strategy.

Handles the full lifecycle:
  - Runtime: build_headers, attempt_recovery (token refresh)
  - Onboarding: initiate (build login URL + store pending), complete (code exchange)
  - DCR: RFC 7591 Dynamic Client Registration

All redirect-flow state (PKCE, HMAC-signed state param, pending store)
is internal to this strategy — no external login/exchange services needed.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client

from mas.core.auth.ports import AuthStrategy, AuthChallenge, CompletionResult, HttpClient
from mas.core.auth.credentials.ports import ServerConfigStore
from mas.core.auth.credentials.models import (
    StoredCredential, TokenSet, RecoveryResult,
)
from mas.core.auth.errors import (
    AuthNotConfiguredError,
    ClientRegistrationError,
    InvalidStateError,
    FlowStateNotFoundError,
    TokenEndpointError,
    TokenRefreshError,
)

from mas.core.auth.strategies.oauth2.config import OAuth2Config
from mas.core.auth.strategies.oauth2.state_manager import OAuthStateManager
from mas.core.auth.strategies.oauth2.models import FlowState, FlowStateStore

logger = logging.getLogger(__name__)


class OAuth2Strategy(AuthStrategy):
    """OAuth 2.1 — Authorization Code + PKCE.

    Self-contained: owns login URL construction, pending-state management,
    code exchange, token refresh, and optional DCR.
    """

    def __init__(
        self,
        pending_store: Optional[FlowStateStore] = None,
        state_manager: Optional[OAuthStateManager] = None,
        callback_url: str = "",
        client_config_store: Optional["ServerConfigStore"] = None,
        http_client: Optional["HttpClient"] = None,
    ):
        self._pending = pending_store
        self._state_mgr = state_manager
        self._callback_url = callback_url
        self._configs = client_config_store
        self._http_client = http_client

    @property
    def scheme_type(self) -> str:
        from mas.core.enums import SchemeType
        return SchemeType.OAUTH2

    # ── Runtime ──────────────────────────────────────────────────────

    def build_headers(self, credential: StoredCredential) -> Dict[str, str]:
        return {"Authorization": f"Bearer {credential.access_token}"}

    async def attempt_recovery(
        self,
        credential: StoredCredential,
        config: Dict[str, Any],
    ) -> RecoveryResult:
        if not credential.refresh_token:
            return RecoveryResult(
                recovered=False,
                should_retry=False,
                reason="No refresh token available; re-authentication required",
            )

        try:
            new_tokens = await self._refresh(config, credential.refresh_token)
        except TokenRefreshError as exc:
            return RecoveryResult(
                recovered=False,
                should_retry=False,
                reason=f"Token refresh failed: {exc}",
            )

        return RecoveryResult(
            recovered=True,
            should_retry=True,
            reason="Token refreshed successfully",
            new_token_set=new_tokens,
        )

    # ── Onboarding: initiate ─────────────────────────────────────────

    async def initiate(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> AuthChallenge:
        """Build an OAuth2 login URL with PKCE + signed state.

        Also handles auto-registration (DCR) if no client_id is present.
        The strategy owns state creation and pending-store writes.
        """
        if not config.get("client_id"):
            config = await self._try_auto_register(user_id, server_identifier, config)

        if not config or not config.get("client_id"):
            raise AuthNotConfiguredError(
                "No client_id available and dynamic registration failed"
            )

        cfg = OAuth2Config.from_dict(config)
        if not cfg.authorization_endpoint:
            raise AuthNotConfiguredError("No authorization_endpoint in config")

        if self._state_mgr:
            state = self._state_mgr.create_state({
                "user_id": user_id,
                "server_identifier": server_identifier,
                "protocol_type": "oauth2",
            })
        else:
            state = secrets.token_urlsafe(32)

        code_verifier = secrets.token_urlsafe(48)

        client = AsyncOAuth2Client(
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
            code_challenge_method="S256",
        )

        extra: Dict[str, Any] = {}
        if cfg.resource_uri:
            extra["resource"] = cfg.resource_uri
        extra.update(cfg.extra_authorize_params)

        url, _ = client.create_authorization_url(
            cfg.authorization_endpoint,
            state=state,
            redirect_uri=self._callback_url,
            scope=" ".join(cfg.scopes) if cfg.scopes else None,
            code_verifier=code_verifier,
            **extra,
        )
        await client.aclose()

        if self._pending:
            self._pending.save(FlowState(
                state_hash=OAuthStateManager.hash_state(state),
                user_id=user_id,
                server_identifier=server_identifier,
                redirect_uri=self._callback_url,
                code_verifier=code_verifier,
                protocol_type="oauth2",
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
                extra={k: v for k, v in config.items() if k in (
                    "client_id", "client_secret", "token_endpoint",
                    "authorization_endpoint", "scopes", "resource_uri",
                )},
            ))

        return AuthChallenge.consent(
            url=url,
            flow_id=state,
            scopes=cfg.scopes,
            server_identifier=server_identifier,
        )

    # ── Onboarding: complete ─────────────────────────────────────────

    async def complete(
        self,
        raw_callback_data: Dict[str, Any],
    ) -> CompletionResult:
        """Validate state, consume pending flow, exchange code for tokens.

        The strategy fully owns callback handling — no service-level
        knowledge of OAuth2 internals is needed.
        """
        code = raw_callback_data["code"]
        state = raw_callback_data["state"]

        if self._state_mgr:
            try:
                self._state_mgr.validate_state(state)
            except ValueError as exc:
                raise InvalidStateError(f"Invalid state: {exc}") from exc

        if not self._pending:
            raise AuthNotConfiguredError("No pending store configured")

        pending = self._pending.consume(OAuthStateManager.hash_state(state))
        if pending is None:
            raise FlowStateNotFoundError(
                "No pending auth for this state (already consumed or expired)"
            )

        config = {**pending.extra, "protocol_type": pending.protocol_type}
        cfg = OAuth2Config.from_dict(config)

        try:
            async with AsyncOAuth2Client(
                client_id=cfg.client_id,
                client_secret=cfg.client_secret,
                token_endpoint_auth_method=cfg.token_endpoint_auth_method,
            ) as client:
                token = await client.fetch_token(
                    cfg.token_endpoint,
                    grant_type="authorization_code",
                    code=code,
                    redirect_uri=pending.redirect_uri,
                    code_verifier=pending.code_verifier,
                )
        except Exception as exc:
            raise TokenEndpointError(f"Code exchange failed: {exc}") from exc

        token_set = _to_token_set(token)

        return CompletionResult(
            token_set=token_set,
            user_id=pending.user_id,
            server_identifier=pending.server_identifier,
            scheme_type="oauth2",
            scopes=token_set.scope.split() if token_set.scope else [],
        )

    # ── RFC 7591 Dynamic Client Registration ──────────────────────────

    async def register_client(
        self,
        registration_endpoint: str,
        client_name: str = "UnifAI",
        redirect_uris: Optional[List[str]] = None,
        token_endpoint_auth_method: str = "none",
    ) -> Dict[str, Any]:
        body: Dict[str, Any] = {
            "client_name": client_name,
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": token_endpoint_auth_method,
        }
        if redirect_uris:
            body["redirect_uris"] = redirect_uris

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    registration_endpoint, json=body,
                    headers={"Accept": "application/json"},
                )
        except Exception as exc:
            raise ClientRegistrationError(f"DCR request failed: {exc}") from exc

        if resp.status_code >= 400:
            try:
                data = resp.json()
                detail = data.get("error_description", data.get("error", ""))
            except Exception:
                detail = resp.text
            raise ClientRegistrationError(
                f"DCR returned {resp.status_code}: {detail}"
            )

        data = resp.json()
        if "client_id" not in data:
            raise ClientRegistrationError("DCR response missing client_id")
        return data

    # ── Internal ──────────────────────────────────────────────────────

    async def _refresh(self, config: Dict[str, Any], refresh_token: str) -> TokenSet:
        cfg = OAuth2Config.from_dict(config)
        try:
            async with AsyncOAuth2Client(
                client_id=cfg.client_id,
                client_secret=cfg.client_secret,
                token_endpoint_auth_method=cfg.token_endpoint_auth_method,
            ) as client:
                token = await client.fetch_token(
                    cfg.token_endpoint,
                    grant_type="refresh_token",
                    refresh_token=refresh_token,
                )
        except Exception as exc:
            raise TokenRefreshError(f"Refresh failed: {exc}") from exc
        return _to_token_set(token)

    async def _try_auto_register(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Attempt RFC 7591 Dynamic Client Registration."""
        if self._configs and server_identifier:
            existing = self._configs.find_by_server(user_id, server_identifier)
            if existing and existing.client_id:
                return existing.model_dump()

        reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint and self._http_client:
            from mas.core.auth.strategies.oauth2.detection import OAuth2DetectionStrategy
            as_meta = await OAuth2DetectionStrategy._fetch_as_metadata(
                server_identifier, self._http_client,
            )
            if as_meta:
                config = {**config, **as_meta}
                reg_endpoint = config.get("registration_endpoint")

        if not reg_endpoint:
            return config

        redirect_uris = [self._callback_url] if self._callback_url else None
        supported_methods = config.get("token_endpoint_auth_methods_supported", [])
        auth_method = supported_methods[0] if supported_methods else "none"

        try:
            result = await self.register_client(
                registration_endpoint=reg_endpoint,
                redirect_uris=redirect_uris,
                token_endpoint_auth_method=auth_method,
            )

            client_id = result.get("client_id")
            if not client_id:
                return config

            new_config = {
                **config,
                "client_id": client_id,
                "client_secret": result.get("client_secret"),
                "server_identifier": server_identifier,
            }

            if self._configs and server_identifier:
                from mas.core.auth.credentials.models import ClientConfig
                self._configs.save(user_id, ClientConfig(
                    client_id=client_id,
                    client_secret=result.get("client_secret"),
                    authorization_endpoint=config.get("authorization_endpoint", ""),
                    token_endpoint=config.get("token_endpoint", ""),
                    token_endpoint_auth_method=auth_method,
                    scopes=config.get("scopes_supported", []),
                    resource_uri=config.get("resource_uri"),
                    server_identifier=server_identifier,
                ))
                logger.info(
                    "Auto-registered OAuth client for server=%s client_id=%s",
                    server_identifier, client_id,
                )

            return new_config

        except Exception as exc:
            logger.warning("Dynamic client registration failed: %s", exc)
            return config


def _to_token_set(token: dict) -> TokenSet:
    """Convert authlib's token dict to our domain TokenSet."""
    expires_at = None
    if "expires_at" in token:
        try:
            expires_at = datetime.fromtimestamp(float(token["expires_at"]), tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            pass
    elif "expires_in" in token:
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(token["expires_in"]))
        except (ValueError, TypeError):
            pass

    return TokenSet(
        access_token=token["access_token"],
        refresh_token=token.get("refresh_token"),
        token_type=token.get("token_type", "Bearer"),
        expires_at=expires_at,
        scope=token.get("scope"),
    )
