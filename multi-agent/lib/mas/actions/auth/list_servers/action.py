"""
auth.list_servers — return auth options for a provider category.

Returns static entries (none, access_token) merged with dynamic entries
from the auth server registry. This powers a single dropdown where the
user picks their auth method directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.credentials.models import StaticAuthMethod
from mas.core.auth.credentials.ports import ServerConfigStore
from mas.core.enums import ResourceCategory
from mas.elements.nodes.a2a_agent.identifiers import Identifier as A2ANodeIdentifier
from mas.elements.providers.a2a_client.identifiers import Identifier as A2AIdentifier
from mas.elements.providers.mcp_server_client.identifiers import Identifier as McpIdentifier

logger = logging.getLogger(__name__)

_STATIC_OPTIONS: List[Dict[str, str]] = [
    {"label": "None", "value": StaticAuthMethod.NONE.value},
    {"label": "Access Token", "value": StaticAuthMethod.ACCESS_TOKEN.value},
]


class ListServersInput(BaseActionInput):
    category: str = Field(default="", description="Filter servers by category (e.g. 'a2a', 'mcp')")


class ListServersOutput(BaseActionOutput):
    servers: List[Dict[str, str]] = Field(default_factory=list)


class ListServersAction(BaseAction):
    uid = "auth.list_servers"
    name = "list_servers"
    description = "List available auth options (static + registry) by category"
    action_type = ActionType.DISCOVERY
    input_schema = ListServersInput
    output_schema = ListServersOutput
    version = "1.0.0"
    tags = {"auth", "registry"}
    elements = {
        (ResourceCategory.NODE.value, A2ANodeIdentifier.TYPE),
        (ResourceCategory.PROVIDER.value, A2AIdentifier.TYPE),
        (ResourceCategory.PROVIDER.value, McpIdentifier.TYPE),
    }

    def __init__(self, server_config_store: Optional[ServerConfigStore] = None):
        super().__init__()
        self._store = server_config_store

    async def execute(
        self,
        input_data: ListServersInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> ListServersOutput:
        category = input_data.category
        if not category:
            return ListServersOutput(
                success=False,
                message="Category is required",
                servers=[],
            )

        servers: List[Dict[str, str]] = list(_STATIC_OPTIONS)

        if self._store:
            configs = self._store.list_by_category(category)
            for c in configs:
                servers.append({
                    "label": c.display_name or c.server_identifier,
                    "value": c.server_identifier,
                })

        return ListServersOutput(
            success=True,
            message=f"Found {len(servers)} option(s)",
            servers=servers,
        )
