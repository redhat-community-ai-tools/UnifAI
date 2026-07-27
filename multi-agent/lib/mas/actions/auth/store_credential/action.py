"""
auth.store_credential — persist a user-provided credential.

Used by auth elements where the user supplies the secret directly (API key,
bearer token, etc.) as opposed to OAuth flows where the credential arrives
via external callback.

Connectivity validation is NOT performed here — that responsibility belongs
to the consumer (e.g. mcp.validate_connection) which knows the transport
protocol and can verify the credential properly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import (
    BaseActionInput,
    BaseActionOutput,
    ActionType,
)
from mas.core.auth.service import AuthService
from mas.core.auth.credentials.models import StoredCredential, TokenStatus
from mas.core.enums import ResourceCategory, AuthStatus, AuthErrorCode, SchemeType
from mas.elements.providers.mcp_server_client.identifiers import Identifier

logger = logging.getLogger(__name__)


class StoreCredentialInput(BaseActionInput):
    user_id: str = Field(default="", description="User storing the credential")
    server_url: str = Field(default="", description="Server URL this credential authenticates against")
    credential: str = Field(default="", description="The secret value (API key, token, etc.)")
    scheme_type: str = Field(default=SchemeType.API_KEY, description="Auth scheme type")


class StoreCredentialOutput(BaseActionOutput):
    status: AuthStatus = AuthStatus.ERROR
    authenticated: bool = False
    error_code: Optional[AuthErrorCode] = None


class StoreCredentialAction(BaseAction):
    uid = "auth.store_credential"
    name = "store_credential"
    description = "Store a user-provided credential for a server"
    action_type = ActionType.VALIDATION
    input_schema = StoreCredentialInput
    output_schema = StoreCredentialOutput
    version = "1.0.0"
    tags = {"auth", "credential"}
    elements = {
        (ResourceCategory.PROVIDER.value, Identifier.TYPE),
    }

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as exc:
            return StoreCredentialOutput(
                success=False,
                message=str(exc),
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.UNKNOWN,
            )

    async def execute(
        self,
        input_data: StoreCredentialInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> StoreCredentialOutput:
        user_id = input_data.user_id
        server_url = input_data.server_url
        credential = input_data.credential
        scheme = input_data.scheme_type

        if not user_id:
            return StoreCredentialOutput(
                success=False,
                message="User ID is required",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.MISSING_USER_ID,
            )

        if not server_url:
            return StoreCredentialOutput(
                success=False,
                message="Server URL is required",
                status=AuthStatus.NOT_CONFIGURED,
                error_code=AuthErrorCode.MISSING_SERVER_ID,
            )

        if not credential:
            return StoreCredentialOutput(
                success=False,
                message="Credential value is required",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.UNKNOWN,
            )

        if not self._auth:
            return StoreCredentialOutput(
                success=False,
                message="Auth service is not available",
                status=AuthStatus.ERROR,
                error_code=AuthErrorCode.AUTH_SERVICE_UNAVAILABLE,
            )

        self._auth.save_credential(StoredCredential(
            user_id=user_id,
            server_identifier=server_url,
            access_token=credential,
            scheme_type=scheme,
            status=TokenStatus.ACTIVE,
            expires_at=None,
        ))

        logger.info(
            "Credential stored for user=%s server=%s scheme=%s",
            user_id, server_url, scheme,
        )

        return StoreCredentialOutput(
            success=True,
            message="Credential stored",
            status=AuthStatus.AUTHENTICATED,
            authenticated=True,
        )
