"""
AuthService — single owner of the credential lifecycle.

Owns: lookup, header building, recovery, onboarding (initiate / complete),
and auth discovery.
Strategies own their protocol-specific logic; this service orchestrates.

Also contains :class:`AuthHandle`, the handle that elements receive
at build time so they can call ``get_headers()`` with no args.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional, Union, TYPE_CHECKING

from .errors import TokenExpiredError
from .credentials.models import (
    StoredCredential, TokenStatus, RecoveryResult, ClientConfig,
)
from .credentials.ports import CredentialStore, ServerConfigStore
from .credentials.credential import AuthCredential
from .ports import AuthStrategy, AuthChallenge

if TYPE_CHECKING:
    from .discovery.detector import AuthDetector
    from .discovery.models import DetectionResult

logger = logging.getLogger(__name__)


class AuthStrategyRegistry:
    """Maps scheme_type strings to AuthStrategy instances."""

    def __init__(self) -> None:
        self._strategies: Dict[str, AuthStrategy] = {}

    def register(self, strategy: AuthStrategy) -> None:
        self._strategies[strategy.scheme_type] = strategy

    def get(self, scheme_type: str) -> AuthStrategy:
        try:
            return self._strategies[scheme_type]
        except KeyError:
            raise ValueError(f"Unknown auth scheme: {scheme_type!r}")


class AuthHandle:
    """Binds AuthService to a specific (user, server) pair.

    Explicitly implements :class:`AuthCredential` so consumers can call
    ``await get_headers()`` / ``await get_token()`` /
    ``await attempt_recovery()`` without passing user_id and
    server_identifier every time.

    Accepts either a plain ``user_id`` string or a zero-arg callable that
    returns the user-id at runtime (deferred resolution for session build
    time, when the executing user isn't known yet).
    """

    def __init__(
        self,
        auth_service: AuthService,
        user_id: Union[str, Callable[[], str]],
        server_identifier: str,
        scheme_type: str = "",
        config: Optional[Dict[str, Any]] = None,
    ):
        self._svc = auth_service
        self._user_id_or_resolver = user_id
        self._server_id = server_identifier
        self._scheme_type = scheme_type
        self._config = config or {}

    @property
    def _user_id(self) -> str:
        uid = self._user_id_or_resolver
        if isinstance(uid, str):
            return uid
        try:
            return uid()
        except RuntimeError:
            return ""

    async def get_headers(self) -> Dict[str, str]:
        return await self._svc.get_headers(
            self._user_id, self._server_id, self._config,
            scheme_type=self._scheme_type,
        )

    async def get_token(self) -> str:
        token = await self._svc.get_valid_token(
            self._user_id, self._server_id, self._config,
            scheme_type=self._scheme_type,
        )
        if not token:
            raise TokenExpiredError("No valid token")
        return token

    async def attempt_recovery(self) -> RecoveryResult:
        return await self._svc.attempt_recovery(
            self._user_id, self._server_id, self._config,
        )


class AuthService:

    def __init__(
        self,
        credential_store: CredentialStore,
        strategy_registry: AuthStrategyRegistry,
        server_config_store: Optional[ServerConfigStore] = None,
        detector: Optional[AuthDetector] = None,
    ):
        self._store = credential_store
        self._strategies = strategy_registry
        self._configs = server_config_store
        self._detector = detector

    # ── Credential CRUD (sync — pure DB, no external I/O) ────────────

    def get_credential(
        self, user_id: str, server_identifier: str, scheme_type: str = "",
    ) -> Optional[StoredCredential]:
        if not user_id or not server_identifier:
            return None
        return self._store.find_by_server(user_id, server_identifier, scheme_type)

    def save_credential(self, credential: StoredCredential) -> None:
        self._store.upsert(credential)

    def delete_credential(self, user_id: str, server_identifier: str) -> None:
        if user_id and server_identifier:
            self._store.delete(user_id, server_identifier)

    def update_status(
        self, user_id: str, server_identifier: str, status: TokenStatus,
    ) -> None:
        cred = self._store.find_by_server(user_id, server_identifier)
        if cred:
            self._store.update_status(
                cred.user_id, cred.server_identifier, status.value,
            )

    def get_client_config(
        self, user_id: str, server_identifier: str,
    ) -> Optional[ClientConfig]:
        if not self._configs:
            return None
        return self._configs.find_by_server(user_id, server_identifier)

    # ── Token access (async — may trigger refresh I/O) ────────────────

    async def get_valid_token(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
        scheme_type: str = "",
    ) -> Optional[str]:
        """Return a valid access token, attempting recovery if expired."""
        cred = self.get_credential(user_id, server_identifier, scheme_type)
        if cred and cred.is_valid():
            return cred.access_token

        if cred:
            recovery = await self.attempt_recovery(user_id, server_identifier, config)
            if recovery.recovered and recovery.new_token_set:
                return recovery.new_token_set.access_token
        return None

    async def get_headers(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
        scheme_type: str = "",
    ) -> Dict[str, str]:
        cred = self.get_credential(user_id, server_identifier, scheme_type)
        if not cred:
            raise TokenExpiredError(
                f"No credential for user={user_id} server={server_identifier}"
            )

        if not cred.is_valid():
            recovery = await self.attempt_recovery(user_id, server_identifier, config)
            if recovery.recovered:
                cred = self.get_credential(user_id, server_identifier, scheme_type)
            if not cred or not cred.is_valid():
                raise TokenExpiredError(
                    f"Credential expired and recovery failed for server={server_identifier}"
                )

        strategy = self._strategies.get(cred.scheme_type)
        return strategy.build_headers(cred)

    # ── Recovery (async — calls external token endpoint) ──────────────

    async def attempt_recovery(
        self,
        user_id: str,
        server_identifier: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> RecoveryResult:
        """Delegate recovery to the appropriate strategy and persist the result."""
        cred = self.get_credential(user_id, server_identifier)
        if not cred:
            return RecoveryResult(
                recovered=False, should_retry=False,
                reason="No credential found",
            )

        strategy = self._strategies.get(cred.scheme_type)
        resolved = config or self._resolve_config(user_id, server_identifier)

        try:
            result = await strategy.attempt_recovery(cred, resolved)
        except Exception as exc:
            logger.info("Recovery failed for server=%s: %s", server_identifier, exc)
            return RecoveryResult(
                recovered=False, should_retry=False,
                reason=f"Recovery error: {exc}",
            )

        if result.recovered and result.new_token_set:
            updated = StoredCredential(
                id=cred.id,
                user_id=cred.user_id,
                server_identifier=cred.server_identifier,
                access_token=result.new_token_set.access_token,
                refresh_token=result.new_token_set.refresh_token or cred.refresh_token,
                token_type=result.new_token_set.token_type,
                expires_at=result.new_token_set.expires_at or cred.expires_at,
                scopes=cred.scopes,
                scheme_type=cred.scheme_type,
                status=TokenStatus.ACTIVE,
            )
            self._store.upsert(updated)
            logger.debug(
                "Credential recovered for user=%s server=%s",
                cred.user_id, cred.server_identifier,
            )

        return result

    # ── Onboarding — fully scheme-agnostic ────────────────────────────

    async def initiate(
        self,
        user_id: str,
        server_identifier: str,
        scheme_type: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> AuthChallenge:
        """Start credential acquisition — delegates entirely to the strategy."""
        strategy = self._strategies.get(scheme_type)
        resolved = config or self._resolve_config(user_id, server_identifier)
        return await strategy.initiate(user_id, server_identifier, resolved)

    async def complete(
        self,
        raw_callback_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Complete the credential-acquisition flow.

        Delegates entirely to the strategy. The strategy validates state,
        consumes the pending flow, and exchanges for tokens. The service
        just persists the result.
        """
        scheme_type = raw_callback_data.get("scheme_type", "oauth2")
        strategy = self._strategies.get(scheme_type)

        result = await strategy.complete(raw_callback_data)

        self._store.upsert(StoredCredential(
            user_id=result.user_id,
            server_identifier=result.server_identifier,
            access_token=result.token_set.access_token,
            refresh_token=result.token_set.refresh_token,
            token_type=result.token_set.token_type,
            expires_at=result.token_set.expires_at,
            scopes=result.scopes,
            status=TokenStatus.ACTIVE,
            scheme_type=result.scheme_type,
        ))

        logger.info(
            "Token stored for user=%s server=%s",
            result.user_id, result.server_identifier,
        )
        return {"success": True, "server_identifier": result.server_identifier}

    # ── Discovery ─────────────────────────────────────────────────────

    async def discover(
        self,
        url: str,
        response_headers: Optional[Dict[str, str]] = None,
    ) -> Optional[DetectionResult]:
        """Detect what auth a server requires. Returns DetectionResult or None."""
        if not self._detector:
            return None
        return await self._detector.detect(url, response_headers)

    # ── Binding ───────────────────────────────────────────────────────

    def bind(
        self, user_id: str, server_identifier: str, scheme_type: str = "",
    ) -> Optional[AuthCredential]:
        if not user_id or not server_identifier:
            return None
        if not self.get_credential(user_id, server_identifier, scheme_type):
            return None

        config = self._resolve_config(user_id, server_identifier)
        return AuthHandle(
            auth_service=self,
            user_id=user_id,
            server_identifier=server_identifier,
            scheme_type=scheme_type,
            config=config,
        )

    def bind_lazy(
        self,
        user_id_resolver: Callable[[], str],
        server_identifier: str,
        scheme_type: str = "",
    ) -> Optional[AuthCredential]:
        """Create a credential handle with deferred user_id resolution.

        The resolver is called at runtime when the credential is actually
        needed, not at build time.  This keeps the auth layer decoupled
        from execution-context specifics.
        """
        if not server_identifier:
            return None

        config = self._resolve_config("", server_identifier)
        return AuthHandle(
            auth_service=self,
            user_id=user_id_resolver,
            server_identifier=server_identifier,
            scheme_type=scheme_type,
            config=config,
        )

    # ── Internals ─────────────────────────────────────────────────────

    def _resolve_config(
        self, user_id: str, server_identifier: str,
    ) -> Dict[str, Any]:
        cfg = self.get_client_config(user_id, server_identifier)
        return cfg.model_dump() if cfg else {}
