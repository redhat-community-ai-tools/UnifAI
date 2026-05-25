from __future__ import annotations

from typing import List, Optional, Dict, Any, TYPE_CHECKING
from pydantic import HttpUrl, Field
from mas.actions.common.base_action import BaseAction
from mas.actions.common.action_models import BaseActionInput, BaseActionOutput, ActionType
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import Identifier
from mas.elements.providers.mcp_server_client.transport.enums import McpTransportType
from mas.core.enums import ResourceCategory

if TYPE_CHECKING:
    from mas.core.auth.service import AuthService

# Input/Output models for this action
class GetToolsNamesInput(BaseActionInput):
    """Input for MCP tools discovery"""
    mcp_url: HttpUrl
    transport_type: McpTransportType = Field(
        default=McpTransportType.STREAMABLE_HTTP,
        description="Transport protocol for MCP server communication"
    )
    additional_headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HTTP headers to include in MCP server requests"
    )
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")


class GetToolsNamesOutput(BaseActionOutput):
    """Output for MCP tools discovery"""
    tool_names: List[str] = []
    total_count: int = 0


class GetToolsNamesAction(BaseAction):
    uid = "mcp.get_tools_names"
    name = "get_tools_names"
    description = "Retrieve the list of available tool names from the MCP server"
    action_type = ActionType.DISCOVERY
    input_schema = GetToolsNamesInput
    output_schema = GetToolsNamesOutput
    version = "1.1.0"
    tags = {"mcp", "discovery", "tools"}
    elements = {(ResourceCategory.PROVIDER.value, Identifier.TYPE)}

    def __init__(self, factory: McpProviderFactory = None, auth_service: Optional[AuthService] = None):
        """
        Initialize action with optional factory injection.
        
        Args:
            factory: McpProviderFactory instance (creates default if not provided)
        """
        super().__init__()
        self._factory = factory or McpProviderFactory()
        self._auth_service = auth_service

    async def execute(
        self,
        input_data: GetToolsNamesInput,
        context: Optional[Dict[str, Any]] = None,
    ) -> GetToolsNamesOutput:
        """
        Execute tools discovery asynchronously.
        
        Args:
            input_data: Validated discovery input
            context: Optional execution context (element configs, etc.)
            
        Returns:
            Discovery result with tool names and count
        """
        try:
            config = McpProviderConfig(
                mcp_url=input_data.mcp_url,
                transport_type=input_data.transport_type,
                additional_headers=input_data.additional_headers,
            )

            auth = None
            if self._auth_service and input_data.user_id:
                lookup_id = input_data.server_identifier or str(input_data.mcp_url)
                auth = self._auth_service.bind(input_data.user_id, lookup_id)

            provider = await self._factory.create_async(config, auth_credential=auth)
            tools = provider.get_tools()
            tool_names = [tool.name for tool in tools]

            return GetToolsNamesOutput(
                success=True,
                message=f"Found {len(tool_names)} tools",
                tool_names=tool_names,
                total_count=len(tool_names)
            )

        except Exception as e:
            return GetToolsNamesOutput(
                success=False,
                message=f"Failed to retrieve tools: {str(e)}",
                tool_names=[],
                total_count=0
            )
