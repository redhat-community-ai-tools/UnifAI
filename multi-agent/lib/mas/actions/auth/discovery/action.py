"""
auth.discovery — discover auth requirements and initiate sign-in.

For the sign-in flow: discovers the auth server from an MCP URL,
checks for existing credentials, and initiates OAuth if needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory, AuthStatus, AuthErrorCode
from mas.elements.providers.mcp_server_client.identifiers import Identifier

logger = logging.getLogger(__name__)


class DiscoveryInput(BaseActionInput):
    user_id: str = Field(default="")
    mcp_url: str = Field(default="")
    server_identifier: str = Field(default="")


class DiscoveryOutput(BaseActionOutput):
    status: AuthStatus = AuthStatus.NOT_CONFIGURED
    authenticated: bool = False
    server_identifier: str = ""
    scheme_type: str = ""
    challenge: Optional[Dict[str, Any]] = None
    error_code: Optional[AuthErrorCode] = None
    form_updates: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)


class DiscoveryAction(BaseAction):
    uid = "auth.discovery"
    name = "discovery"
    description = "Discover auth requirements and initiate sign-in"
    action_type = ActionType.VALIDATION
    input_schema = DiscoveryInput
    output_schema = DiscoveryOutput
    version = "1.0.0"
    tags = {"auth", "discovery"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as exc:
            return DiscoveryOutput(
                success=False, message=str(exc),
                error_code=AuthErrorCode.UNKNOWN,
            )

    async def execute(self, input_data, context=None):
        user_id = input_data.user_id
        server_id = input_data.server_identifier

        if not user_id or not self._auth:
            return DiscoveryOutput(
                success=False, message="User ID required",
                error_code=AuthErrorCode.MISSING_USER_ID,
            )

        # Step 1: Discover if server_identifier unknown
        if not server_id:
            if not input_data.mcp_url:
                return DiscoveryOutput(
                    success=False, message="MCP URL required",
                    error_code=AuthErrorCode.MISSING_SERVER_ID,
                )
            detection = await self._auth.discover(input_data.mcp_url)
            if not detection:
                return DiscoveryOutput(
                    success=False,
                    message="No authentication requirements detected",
                )
            server_id = detection.server_identifier
            scheme_type = detection.protocol_type
        else:
            cred = self._auth.get_credential(user_id, server_id)
            scheme_type = cred.scheme_type if cred else "oauth2"

        # Step 2: Already authenticated?
        token = await self._auth.get_valid_token(user_id, server_id)
        if token:
            sealed = self._auth.seal_token(token)
            return DiscoveryOutput(
                success=True,
                message="Authenticated",
                status=AuthStatus.AUTHENTICATED,
                authenticated=True,
                server_identifier=server_id,
                scheme_type=scheme_type,
                form_updates={
                    "credential_token": sealed,
                    "server_identifier": server_id,
                    "scheme_type": scheme_type,
                },
                actions=[{
                    "uid": "auth.sign_out",
                    "label": "Sign Out",
                    "style": "danger",
                    "dependencies": {
                        "server_identifier": "server_identifier",
                    },
                }],
            )

        # Step 3: Initiate sign-in
        config = self._auth.get_client_config("", server_id)
        login_config = config.model_dump() if config else {}

        try:
            challenge = await self._auth.initiate(
                user_id, server_id,
                scheme_type=scheme_type,
                config=login_config,
            )
            return DiscoveryOutput(
                success=True,
                message="Sign in required",
                status=AuthStatus.CHALLENGE,
                server_identifier=server_id,
                scheme_type=scheme_type,
                challenge=challenge.to_response(),
                form_updates={
                    "server_identifier": server_id,
                    "scheme_type": scheme_type,
                },
            )
        except Exception as exc:
            logger.warning("Auth initiation failed for server=%s: %s", server_id, exc)
            return DiscoveryOutput(
                success=False, message=str(exc),
                server_identifier=server_id,
                error_code=AuthErrorCode.INITIATION_FAILED,
            )
