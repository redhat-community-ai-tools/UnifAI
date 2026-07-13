"""
MCP validate_connection action.

Connectivity probe. Uses credential_token from the form if provided,
otherwise falls back to stored credential via bind(server_identifier).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

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
    credential_token: Optional[str] = Field(default=None)
    auth_method: str = Field(default="")
    transport_type: McpTransportType = Field(default=McpTransportType.STREAMABLE_HTTP)
    additional_headers: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionOutput(BaseActionOutput):
    is_reachable: bool = False
    authenticated: bool = False
    status: str = ""
    server_identifier: str = ""
    response_time_ms: float = 0.0
    form_updates: Dict[str, Any] = Field(default_factory=dict)


class ValidateConnectionAction(BaseAction):
    uid = "mcp.validate_connection"
    name = "validate_connection"
    description = "Validate MCP server connectivity"
    action_type = ActionType.VALIDATION
    input_schema = ValidateConnectionInput
    output_schema = ValidateConnectionOutput
    version = "10.0.0"
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
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
            )

    async def execute(self, input_data, context=None):
        start = time.time()
        mcp_url = str(input_data.mcp_url)
        server_id = input_data.server_identifier

        raw_token = input_data.credential_token
        credential = self._auth.unseal_token(raw_token) if (self._auth and raw_token) else raw_token

        # Fallback: if no token provided but we have user+server, bind stored credential
        auth_cred = None
        is_sign_in = input_data.auth_method == "sign_in"
        if not credential and self._auth and input_data.user_id and server_id and is_sign_in:
            auth_cred = self._auth.bind(input_data.user_id, server_id)

        config = McpProviderConfig(
            mcp_url=input_data.mcp_url,
            bearer_token=credential or None,
            transport_type=input_data.transport_type,
            additional_headers=input_data.additional_headers,
        )

        try:
            await self._factory.create_async(config, auth_credential=auth_cred)
            elapsed = (time.time() - start) * 1000
            resolved_id = server_id or mcp_url
            return ValidateConnectionOutput(
                success=True,
                message=f"Connected ({elapsed:.0f}ms)",
                is_reachable=True,
                authenticated=bool(credential or auth_cred),
                status="",
                server_identifier=resolved_id,
                response_time_ms=elapsed,
                form_updates={"server_identifier": resolved_id},
            )
        except TimeoutError:
            return ValidateConnectionOutput(
                success=False, message="Connection timeout",
                is_reachable=False,
                response_time_ms=(time.time() - start) * 1000,
            )
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            error_msg = str(e)
            if "401" in error_msg or "Unauthorized" in error_msg:
                return ValidateConnectionOutput(
                    success=True,
                    message="Server rejected credentials — sign in again",
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=mcp_url,
                    response_time_ms=elapsed,
                )
            if "403" in error_msg or "Forbidden" in error_msg:
                return ValidateConnectionOutput(
                    success=True,
                    message="Authenticated but not authorized — check scopes",
                    is_reachable=True,
                    authenticated=False,
                    status="auth_required",
                    server_identifier=mcp_url,
                    response_time_ms=elapsed,
                )
            return ValidateConnectionOutput(
                success=False, message=f"Connection failed: {e}",
                is_reachable=False,
                response_time_ms=elapsed,
            )
