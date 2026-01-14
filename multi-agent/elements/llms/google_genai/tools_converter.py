from langchain_core.tools import StructuredTool
from langchain_core.tools import BaseTool as LangChainBaseTool
from ...tools.common.converter import LangChainToolsConverter
from ...tools.common.base_tool import BaseTool
from .schema_sanitizer import SchemaSanitizer


class GoogleGenAIToolsConverter(LangChainToolsConverter):
    """Converter with schema sanitization for Google GenAI compatibility."""

    @classmethod
    def _convert_tool(cls, tool: BaseTool) -> LangChainBaseTool:
        """Convert tool with sanitized schema for Google GenAI."""
        schema = tool.get_args_schema_json()

        if isinstance(schema, dict):
            schema = SchemaSanitizer.sanitize(schema)

        return StructuredTool.from_function(
            func=tool.run,
            args_schema=schema,
            name=tool.name,
            description=tool.description,
            coroutine=tool.arun
        )
