from typing import List
from langchain_core.tools import StructuredTool
from langchain_core.tools import BaseTool as LangChainBaseTool
from .base_tool import BaseTool


class LangChainToolsConverter:
    """Base converter for internal tools to LangChain format."""

    @classmethod
    def to_lc(cls, tools: List[BaseTool]) -> List[LangChainBaseTool]:
        if not tools:
            return []
        return [cls._convert_tool(tool) for tool in tools]

    @classmethod
    def _convert_tool(cls, tool: BaseTool) -> LangChainBaseTool:
        """Convert a single tool. Override to customize conversion."""
        return StructuredTool.from_function(
            func=tool.run,
            args_schema=tool.get_args_schema_json(),
            name=tool.name,
            description=tool.description,
            coroutine=tool.arun
        )
