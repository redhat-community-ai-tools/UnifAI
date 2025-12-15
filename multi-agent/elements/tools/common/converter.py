from typing import List
from langchain_core.tools import StructuredTool
from langchain_core.tools import BaseTool as LangChainBaseTool
from .base_tool import BaseTool


class LangChainToolsConverter:

    @staticmethod
    def to_lc(tools: List[BaseTool]) -> List[LangChainBaseTool]:
        lc_tools = []

        if tools:
            for tool in tools:
                lc_tools.append(StructuredTool.from_function(func=tool.run,
                                                             args_schema=tool.get_args_schema_json(),
                                                             name=tool.name,
                                                             description=tool.description,
                                                             coroutine=tool.arun))
        return lc_tools
