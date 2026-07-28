"""
A2A validate_connection action.

Reachability probe with auth awareness. Uses credential_token from the form
if provided, otherwise falls back to stored credentials via AuthService.
Expired / missing SSO sessions return status=auth_required (yellow in UI).
"""

from __future__ import annotations

import ipaddress
import logging
import time
from typing import Any, Dict, Optional

import anyio
from pydantic import Field, HttpUrl

from mas.actions.common.action_models import ActionType, BaseActionInput, BaseActionOutput
from mas.actions.common.base_action import BaseAction
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory
from mas.elements.nodes.a2a_agent.identifiers import Identifier as NodeIdentifier
from mas.elements.providers.a2a_client import A2AClient
from mas.elements.providers.a2a_client.identifiers import Identifier as ProviderIdentifier

logger = logging.getLogger(__name__)

_STATIC_AUTH = StaticAuthMethod.values()


def _endpoint_label(url: HttpUrl) -> str:
    """Return host[:port] only — drop userinfo/path/query/fragment for logs/IDs.

    IPv6 literals are bracketed when a port is present (e.g. ``[::1]:8000``).
    """
    host = url.host or ""
    if url.port is None:
        return host
    try:
        if ipaddress.ip_address(host).version == 6:
            return f"[{host}]:{url.port}"
    except ValueError:
        pass
    return f"{host}:{url.port}"


class ValidateConnectionInput(BaseActionInput):
    base_url: HttpUrl
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")
    credential_token: Optional[str] = Field(default=None)
    bearer_token: Optional[str] = Field(default=None)
    auth_method: str = Field(default=StaticAuthMethod.NONE.value)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    status: str = ""
    server_identifier: str = ""
    response_time_ms: float = 0.0


class ValidateConnectionAction(BaseAction):
    """
    Validate A2A endpoint reachability and credential state.

    - ``none``: reachability only
    - ``access_token``: require a bearer/credential token
    - registry SSO: resolve via form token or AuthService; expired → auth_required
    """

    uid = "a2a.validate_connection"
    name = "validate_connection"
    description = "Validate that the A2A agent endpoint is reachable and authenticated"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "2.0.0"
    tags = {"a2a", "validation", "connectivity"}
    elements = {
        (ResourceCategory.NODE.value, NodeIdentifier.TYPE),
        (ResourceCategory.PROVIDER.value, ProviderIdentifier.TYPE),
    }

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {e}",
                is_reachable=False,
            )

    async def _resolve_token(
        self, input_data: ValidateConnectionInput
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Returns (token, auth_required_message).
        auth_required_message is set when auth is expected but no valid token exists.
        """
        auth_method = input_data.auth_method or StaticAuthMethod.NONE.value

        if auth_method == StaticAuthMethod.NONE.value:
            return None, None

        if auth_method == StaticAuthMethod.ACCESS_TOKEN.value:
            raw = input_data.credential_token or input_data.bearer_token
            token = self._auth.unseal_token(raw) if (self._auth and raw) else raw
            if token:
                return token, None
            return None, "Bearer token required — provide a token or sign in"

        # Registry SSO: AuthService is the source of truth (expiry + refresh).
        # Do not fall back to a sealed form credential_token — that can be stale
        # and make a public agent-card fetch look "green" while the session is dead.
        server_id = input_data.server_identifier or auth_method
        if self._auth and input_data.user_id and server_id:
            token = await self._auth.get_valid_token(input_data.user_id, server_id)
            if token:
                return token, None

        return None, "Session expired — sign in again"

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidateConnectionOutput:
        start = time.time()
        auth_method = input_data.auth_method or StaticAuthMethod.NONE.value
        server_id = input_data.server_identifier or (
            auth_method if auth_method not in _STATIC_AUTH else ""
        )

        token, auth_required_msg = await self._resolve_token(input_data)

        headers: Dict[str, str] = {}
        if input_data.additional_headers:
            headers.update({str(k): str(v) for k, v in input_data.additional_headers.items()})
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            with anyio.fail_after(10.0):
                async with A2AClient(
                    base_url=input_data.base_url,
                    headers=headers or None,
                ) as client:
                    _ = client.agent_card

            elapsed = (time.time() - start) * 1000

            if auth_required_msg:
                return ValidateConnectionOutput(
                    success=True,
                    message=auth_required_msg,
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=server_id,
                    response_time_ms=elapsed,
                )

            return ValidateConnectionOutput(
                success=True,
                message=f"Connection successful ({elapsed:.0f}ms)",
                is_reachable=True,
                authenticated=bool(token) if auth_method != StaticAuthMethod.NONE.value else False,
                status="",
                server_identifier=server_id,
                response_time_ms=elapsed,
            )

        except TimeoutError:
            elapsed = (time.time() - start) * 1000
            logger.warning(
                "a2a.validate_connection timeout host=%s server_identifier=%r "
                "elapsed_ms=%.0f",
                input_data.base_url.host,
                server_id,
                elapsed,
            )
            return ValidateConnectionOutput(
                success=False,
                message="Connection timeout - agent may be unreachable",
                is_reachable=False,
                response_time_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            error_msg = str(e)
            error_l = error_msg.lower()
            safe_id = server_id or _endpoint_label(input_data.base_url)
            if "401" in error_l or "unauthorized" in error_l:
                logger.warning(
                    "a2a.validate_connection auth rejected (401) host=%s "
                    "server_identifier=%r elapsed_ms=%.0f error_type=%s",
                    input_data.base_url.host,
                    safe_id,
                    elapsed,
                    type(e).__name__,
                )
                return ValidateConnectionOutput(
                    success=True,
                    message="Server rejected credentials — sign in again",
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=safe_id,
                    response_time_ms=elapsed,
                )
            if "403" in error_l or "forbidden" in error_l:
                logger.warning(
                    "a2a.validate_connection forbidden (403) host=%s "
                    "server_identifier=%r elapsed_ms=%.0f error_type=%s",
                    input_data.base_url.host,
                    safe_id,
                    elapsed,
                    type(e).__name__,
                )
                return ValidateConnectionOutput(
                    success=True,
                    message="Authenticated but not authorized — check scopes",
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=safe_id,
                    response_time_ms=elapsed,
                )
            logger.exception(
                "a2a.validate_connection failed host=%s server_identifier=%r "
                "elapsed_ms=%.0f",
                input_data.base_url.host,
                server_id,
                elapsed,
            )
            return ValidateConnectionOutput(
                success=False,
                message=f"Connection failed: {error_msg}",
                is_reachable=False,
                response_time_ms=elapsed,
            )
