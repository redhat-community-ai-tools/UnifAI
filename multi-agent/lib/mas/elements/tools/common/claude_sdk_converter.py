from __future__ import annotations

from typing import Any, Dict, List

from claude_agent_sdk import SdkMcpTool, create_sdk_mcp_server

from .base_tool import BaseTool


class ClaudeSDKConverter:
    """Converts domain ``BaseTool`` instances to Claude SDK ``SdkMcpTool``.

    Handles two categories (same as ``LangChainToolsConverter``):
    1. Domain tools — ``args_schema`` is a Pydantic model class.
    2. MCP proxy tools — ``args_schema`` is a raw JSON schema dict from the
       MCP server.
    """

    @classmethod
    def to_sdk(cls, tools: List[BaseTool]) -> List[SdkMcpTool]:
        """Convert domain tools to Claude SDK ``SdkMcpTool`` instances."""
        if not tools:
            return []
        return [cls._convert_tool(tool) for tool in tools]

    @classmethod
    def _convert_tool(cls, tool: BaseTool) -> SdkMcpTool:
        """Convert a single domain tool to an ``SdkMcpTool``."""

        async def handler(args: dict) -> dict:
            result = await tool.arun(**args)
            return {
                "content": [{"type": "text", "text": str(result)}]
            }

        return SdkMcpTool(
            name=tool.name,
            description=tool.description or "",
            input_schema=tool.get_args_schema_json() or {"type": "object"},
            handler=handler,
        )
