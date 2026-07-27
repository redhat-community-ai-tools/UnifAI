from __future__ import annotations

from typing import Any, Dict, List, Optional, Type, Union

from langchain_core.tools import StructuredTool
from langchain_core.tools import BaseTool as LangChainBaseTool
from pydantic import BaseModel

from .base_tool import BaseTool


class LangChainToolsConverter:
    """Converts domain ``BaseTool`` instances to LangChain ``StructuredTool``.

    Handles two categories:
    1. Domain tools — ``args_schema`` is a Pydantic model class, passed directly.
    2. MCP proxy tools — ``args_schema`` is a raw JSON schema dict from the
       MCP server, passed directly (LangChain StructuredTool accepts both).
    """

    @classmethod
    def to_lc(cls, tools: List[BaseTool]) -> List[LangChainBaseTool]:
        if not tools:
            return []
        return [cls._convert_tool(tool) for tool in tools]

    @classmethod
    def _convert_tool(cls, tool: BaseTool) -> LangChainBaseTool:
        """Convert a single domain tool to a LangChain StructuredTool."""
        return StructuredTool(
            name=tool.name,
            description=tool.description or "",
            func=tool.run,
            coroutine=tool.arun,
            args_schema=tool.args_schema,
        )
