"""
auth.sign_out — revoke a stored credential.

Deletes the credential from the store and returns form_updates
to clear auth-related form fields.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.service import AuthService
from mas.core.enums import ResourceCategory
from mas.elements.providers.mcp_server_client.identifiers import Identifier as McpIdentifier
from mas.elements.nodes.a2a_agent.identifiers import Identifier as A2ANodeIdentifier
from mas.elements.providers.a2a_client.identifiers import Identifier as A2AProviderIdentifier

logger = logging.getLogger(__name__)


class SignOutInput(BaseActionInput):
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")


class SignOutOutput(BaseActionOutput):
    signed_out: bool = False
    form_updates: Dict[str, Any] = Field(default_factory=dict)


class SignOutAction(BaseAction):
    uid = "auth.sign_out"
    name = "sign_out"
    description = "Revoke a stored credential"
    action_type = ActionType.VALIDATION
    input_schema = SignOutInput
    output_schema = SignOutOutput
    version = "1.0.0"
    tags = {"auth", "credential"}
    elements = {
        (ResourceCategory.PROVIDER.value, McpIdentifier.TYPE),
        (ResourceCategory.NODE.value, A2ANodeIdentifier.TYPE),
        (ResourceCategory.PROVIDER.value, A2AProviderIdentifier.TYPE),
    }

    def __init__(self, auth_service: Optional[AuthService] = None):
        super().__init__()
        self._auth = auth_service

    def execute_sync(self, input_data, context=None):
        try:
            return super().execute_sync(input_data, context)
        except RuntimeError as exc:
            return SignOutOutput(success=False, message=str(exc))

    async def execute(self, input_data, context=None):
        if not input_data.user_id or not input_data.server_identifier or not self._auth:
            return SignOutOutput(success=False, message="Missing required fields")

        self._auth.delete_credential(input_data.user_id, input_data.server_identifier)

        logger.info(
            "Credential deleted for user=%s server=%s",
            input_data.user_id, input_data.server_identifier,
        )

        return SignOutOutput(
            success=True,
            message="Signed out",
            signed_out=True,
            form_updates={
                "credential_token": "",
                "server_identifier": "",
                "scheme_type": "",
            },
        )
