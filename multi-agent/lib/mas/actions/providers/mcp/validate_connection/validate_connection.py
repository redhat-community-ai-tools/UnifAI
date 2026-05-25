"""
MCP validate_connection action.

Tests a real MCP connection via the factory.
On 401: uses AuthService.discover() + AuthService.initiate() for login.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from pydantic import HttpUrl, Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType

logger = logging.getLogger(__name__)


class ValidateConnectionInput(BaseActionInput):
    mcp_url: HttpUrl
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")
    bearer_token: Optional[str] = Field(default=None)
    auth_method: str = Field(default="access_token")
    scheme_type: str = Field(default="")
    transport_type: McpTransportType = Field(default=McpTransportType.STREAMABLE_HTTP)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    auth_required: bool = False
    status: str = ""
    server_identifier: str = ""
    scheme_type: str = ""
    authorization_url: Optional[str] = None
    scopes: List[str] = Field(default_factory=list)
    response_time_ms: float = 0.0
    challenge: Optional[Dict[str, Any]] = None


class ValidateConnectionAction(BaseAction):
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate MCP server connection and authentication status"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "6.0.0"
    tags = {"mcp", "validation", "connectivity"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def __init__(
        self,
        factory: Optional[McpProviderFactory] = None,
        auth_service: Optional[AuthService] = None,
    ):
        super().__init__()
        self._factory = factory or McpProviderFactory()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as e:
            if "cancel scope" in str(e).lower():
                return self._handle_auth_required_sync(input_data)
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
            )

    async def execute(
        self,
        input_data: ValidateConnectionInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ValidateConnectionOutput:
        start = time.time()
        user_id = input_data.user_id
        server_id = input_data.server_identifier
        auth_method = input_data.auth_method

        scheme_type = input_data.scheme_type

        auth_cred = None
        if auth_method != "access_token" and self._auth and user_id and server_id:
            lookup_id = server_id or str(input_data.mcp_url)
            auth_cred = self._auth.bind(user_id, lookup_id, scheme_type=scheme_type)

        config = McpProviderConfig(
            mcp_url=input_data.mcp_url,
            bearer_token=input_data.bearer_token,
            transport_type=input_data.transport_type,
            additional_headers=input_data.additional_headers,
        )

        try:
            import anyio
            with anyio.fail_after(10.0):
                await self._factory.create_async(config, auth_credential=auth_cred)
            elapsed = (time.time() - start) * 1000

            if auth_method == "access_token":
                self._establish_credential(input_data)

            return ValidateConnectionOutput(
                success=True, message=f"Connected ({elapsed:.0f}ms)",
                is_reachable=True,
                authenticated=bool(auth_cred) or bool(input_data.bearer_token),
                status="authenticated" if (auth_cred or input_data.bearer_token) else "",
                server_identifier=server_id or str(input_data.mcp_url),
                response_time_ms=elapsed,
            )

        except TimeoutError:
            return ValidateConnectionOutput(
                success=False, message="Connection timeout",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )

        except Exception as e:
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )

    def _establish_credential(self, input_data: ValidateConnectionInput) -> None:
        """Persist a validated bearer token to the credential store.

        Called after a successful connection proves the token is valid.
        Ensures subsequent operations (get_tools, resource validation,
        runtime execution) can retrieve the credential by mcp_url.
        """
        if not input_data.bearer_token or not self._auth or not input_data.user_id:
            return

        try:
            from mas.core.auth.credentials.models import StoredCredential, TokenStatus

            self._auth.save_credential(StoredCredential(
                user_id=input_data.user_id,
                server_identifier=str(input_data.mcp_url),
                access_token=input_data.bearer_token,
                scheme_type="api_key",
                status=TokenStatus.ACTIVE,
                expires_at=None,
            ))
        except Exception as exc:
            logger.warning("Failed to establish credential: %s", exc)

    def _handle_auth_required_sync(
        self, input_data: ValidateConnectionInput,
    ) -> ValidateConnectionOutput:
        """Handle 401: discover auth and retry with stored credentials.

        Skips discovery and store lookup when auth_method is access_token.
        """
        auth_method = input_data.auth_method
        server_id = input_data.server_identifier
        user_id = input_data.user_id
        scheme_type = input_data.scheme_type
        scopes: List[str] = []

        if auth_method == "access_token":
            return ValidateConnectionOutput(
                success=True,
                message="Authentication required — provide an access token",
                status="auth_required", is_reachable=True, auth_required=True,
                server_identifier=server_id,
            )

        from global_utils.utils.async_bridge import get_async_bridge

        if not server_id and self._auth:
            try:
                with get_async_bridge() as bridge:
                    detection = bridge.run(
                        self._auth.discover(str(input_data.mcp_url))
                    )
                    if detection:
                        server_id = detection.server_identifier
                        scheme_type = detection.protocol_type
                        scopes = detection.scopes_supported
            except Exception as exc:
                logger.debug("Auth discovery failed: %s", exc)

        if server_id and user_id and self._auth:
            try:
                with get_async_bridge() as bridge:
                    token = bridge.run(self._auth.get_valid_token(user_id, server_id, scheme_type=scheme_type))
            except Exception as exc:
                logger.warning("Token lookup/refresh failed: %s", exc)
                token = None
            logger.info(
                "Auth retry: user=%s server=%s token_found=%s",
                user_id, server_id, bool(token),
            )
            if token:
                auth_cred = self._auth.bind(user_id, server_id, scheme_type=scheme_type)
                config = McpProviderConfig(
                    mcp_url=input_data.mcp_url,
                    transport_type=input_data.transport_type,
                    additional_headers=input_data.additional_headers,
                )
                try:
                    start = time.time()
                    with get_async_bridge() as bridge:
                        bridge.run(
                            self._factory.create_async(config, auth_credential=auth_cred)
                        )
                    elapsed = (time.time() - start) * 1000
                    return ValidateConnectionOutput(
                        success=True, message=f"Connected ({elapsed:.0f}ms)",
                        is_reachable=True, authenticated=True,
                        status="authenticated",
                        server_identifier=server_id,
                        scheme_type=scheme_type,
                        response_time_ms=elapsed,
                    )
                except Exception as exc:
                    logger.warning(
                        "Authenticated retry failed for server=%s: %s",
                        server_id, exc,
                    )
                    return ValidateConnectionOutput(
                        success=False,
                        message="Authenticated, but the server still rejected the request. "
                                "Check that all required headers are configured in 'Additional Headers'.",
                        status="authenticated_but_rejected",
                        is_reachable=True,
                        authenticated=True,
                        auth_required=False,
                        server_identifier=server_id,
                        scheme_type=scheme_type,
                    )

        return ValidateConnectionOutput(
            success=True,
            message="Authentication required — use the sign in field or provide an access token to authenticate",
            status="auth_required", is_reachable=True, auth_required=True,
            server_identifier=server_id, scheme_type=scheme_type, scopes=scopes,
        )
