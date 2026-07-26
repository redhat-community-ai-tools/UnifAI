from typing import Literal
from pydantic import Field
from mas.core.field_hints import CardHint, CardContext
from mas.elements.tools.common.base_config import BaseToolConfig
from .identifiers import Identifier


class McpProxyToolConfig(BaseToolConfig):
    """
    Configuration for the Mcp Proxy tool.
    """
    type: Literal[Identifier.TYPE] = Identifier.TYPE
    tool_name: str = Field(
        ...,
        description="",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
