"""
auth.list_servers — return pre-configured auth servers filtered by category.

Populates dropdowns in provider configs (A2A, MCP, etc.) with available
identity providers from the auth server registry.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from pydantic import Field

from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.core.auth.credentials.ports import ServerConfigStore
from mas.core.enums import ResourceCategory
from mas.elements.providers.a2a_client.identifiers import Identifier as A2AIdentifier
from mas.elements.providers.mcp_server_client.identifiers import Identifier as McpIdentifier

logger = logging.getLogger(__name__)


class ListServersInput(BaseActionInput):
    category: str = Field(default="", description="Filter servers by category (e.g. 'a2a', 'mcp')")


class ServerEntry(BaseActionOutput):
    label: str
    value: str


class ListServersOutput(BaseActionOutput):
    servers: List[Dict[str, str]] = Field(default_factory=list)


class ListServersAction(BaseAction):
    uid = "auth.list_servers"
    name = "list_servers"
    description = "List pre-configured auth servers by category"
    action_type = ActionType.DISCOVERY
    input_schema = ListServersInput
    output_schema = ListServersOutput
    version = "1.0.0"
    tags = {"auth", "registry"}
    elements = {
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
        if not self._store:
            return ListServersOutput(
                success=False,
                message="Server config store not available",
                servers=[],
            )

        category = input_data.category
        if not category:
            return ListServersOutput(
                success=False,
                message="Category is required",
                servers=[],
            )

        configs = self._store.list_by_category(category)

        servers = [
            {"label": c.display_name or c.server_identifier, "value": c.server_identifier}
            for c in configs
        ]

        return ListServersOutput(
            success=True,
            message=f"Found {len(servers)} server(s)",
            servers=servers,
        )
