from typing import ClassVar, Type, List

from elements.common.base_element_spec import BaseElementSpec
from core.enums import ResourceCategory
from elements.providers.mcp_server_client.config import McpProviderConfig
from elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from elements.providers.mcp_server_client.identifiers import Identifier, META
from elements.providers.mcp_server_client.validator import McpProviderValidator


class McpProviderElementSpec(BaseElementSpec):
    """
    Element specification for MCP Provider.
    
    Provides MCP server connection and management capabilities.
    Note: Actions for MCP operations are now managed independently via the ActionsService.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.PROVIDER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = McpProviderConfig
    factory_cls = McpProviderFactory
    tags = META.tags
    validator_cls = McpProviderValidator