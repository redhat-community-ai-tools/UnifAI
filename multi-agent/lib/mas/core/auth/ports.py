"""
Auth-layer ports — abstract contracts that define the hexagonal boundary.

:class:`AuthStrategy`  — unified interface for ANY auth mechanism.
:class:`AuthChallenge` — scheme-agnostic response returned when credentials
                         must be acquired (consent redirect, form input, etc.).
:class:`HttpClient`    — async HTTP I/O used by strategy adapters.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from mas.core.enums import ChallengeType
from .credentials.models import StoredCredential, TokenSet, RecoveryResult


# ── Strategy port ─────────────────────────────────────────────────────

class AuthStrategy(ABC):
    """Unified contract for any authentication scheme.

    Every strategy implements all four core methods.
    """

    @property
    @abstractmethod
    def scheme_type(self) -> str: ...

    # ── Runtime (using credentials) ──────────────────────────────────

    @abstractmethod
    def build_headers(self, credential: StoredCredential) -> Dict[str, str]:
        """Return HTTP headers for an authenticated request."""
        ...

    @abstractmethod
    async def attempt_recovery(
        self,
        credential: StoredCredential,
        config: Dict[str, Any],
    ) -> RecoveryResult:
        """Credential was rejected — try to self-heal (e.g. token refresh)."""
        ...

    # ── Onboarding (acquiring credentials) ───────────────────────────

    @abstractmethod
    async def initiate(
        self,
        user_id: str,
        server_identifier: str,
        config: Dict[str, Any],
    ) -> AuthChallenge:
        """Start the credential-acquisition flow.

        The strategy owns state creation, pending-store writes, and
        everything else needed to produce an :class:`AuthChallenge`.
        """
        ...

    @abstractmethod
    async def complete(
        self,
        raw_callback_data: Dict[str, Any],
    ) -> "CompletionResult":
        """Finish the credential-acquisition flow.

        The strategy owns state validation, pending-store consumption,
        and token exchange. Returns a :class:`CompletionResult` with
        the tokens and metadata the service needs to persist.
        """
        ...


# ── CompletionResult ─────────────────────────────────────────────────

class CompletionResult(BaseModel):
    """What a strategy returns after completing the auth flow."""
    token_set: TokenSet
    user_id: str
    server_identifier: str
    scheme_type: str
    scopes: List[str] = Field(default_factory=list)


# ── AuthChallenge — scheme-agnostic onboarding responses ─────────────

class AuthChallenge(BaseModel):
    """What the auth layer sends to the UI when credentials must be acquired.

    The ``challenge_type`` discriminator tells the UI how to present it:
      - ``"consent"``  → open redirect URL (OAuth2, SAML)
      - ``"collect"``  → render input form (API key, basic auth)
      - ``"device"``   → show device code + verification URI (future)
    """
    model_config = {"frozen": True}

    challenge_type: str
    flow_id: str = ""
    url: Optional[str] = None
    fields: List[Dict[str, Any]] = Field(default_factory=list)
    device_code: Optional[str] = None
    verification_uri: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    server_identifier: str = ""
    extra: Dict[str, Any] = Field(default_factory=dict)

    def to_response(self) -> Dict[str, Any]:
        """Serialize for the action's HTTP response."""
        resp: Dict[str, Any] = {
            "challenge_type": self.challenge_type,
            "flow_id": self.flow_id,
        }
        if self.url:
            resp["authorization_url"] = self.url
        if self.fields:
            resp["fields"] = self.fields
        if self.device_code:
            resp["device_code"] = self.device_code
        if self.verification_uri:
            resp["verification_uri"] = self.verification_uri
        if self.scopes:
            resp["scopes"] = self.scopes
        if self.server_identifier:
            resp["server_identifier"] = self.server_identifier
        if self.extra:
            resp.update(self.extra)
        return resp

    @classmethod
    def consent(
        cls,
        url: str,
        flow_id: str = "",
        scopes: Optional[List[str]] = None,
        server_identifier: str = "",
    ) -> AuthChallenge:
        return cls(
            challenge_type=ChallengeType.CONSENT,
            url=url,
            flow_id=flow_id,
            scopes=scopes or [],
            server_identifier=server_identifier,
        )

    @classmethod
    def collect(
        cls,
        fields: List[Dict[str, Any]],
        flow_id: str = "",
        server_identifier: str = "",
    ) -> AuthChallenge:
        return cls(
            challenge_type=ChallengeType.COLLECT,
            fields=fields,
            flow_id=flow_id,
            server_identifier=server_identifier,
        )


# ── HTTP I/O port ────────────────────────────────────────────────────

class HttpClient(ABC):

    @abstractmethod
    async def post(
        self,
        url: str,
        *,
        data: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...

    @abstractmethod
    async def get(
        self,
        url: str,
        *,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 10.0,
    ) -> HttpResponse: ...


class HttpResponse:
    """Minimal wrapper so domain code is not coupled to httpx.Response."""

    __slots__ = ("status_code", "body", "headers")

    def __init__(
        self,
        status_code: int,
        body: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
    ):
        self.status_code = status_code
        self.body = body
        self.headers = headers or {}
