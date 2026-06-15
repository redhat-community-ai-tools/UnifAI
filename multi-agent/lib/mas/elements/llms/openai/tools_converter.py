"""
Converter from ``ToolDefinition`` to OpenAI-native tool definitions.

Uses the SDK's own ``ChatCompletionToolParam`` and ``FunctionDefinition``
TypedDicts so the output is type-checked against the API spec — misspelled
keys or wrong value types are caught by the type checker, not at runtime.
"""

from __future__ import annotations

from typing import List, Optional

from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from ...tools.common.tool_definition import ToolDefinition


class OpenAIToolsConverter:
    """Converts ``ToolDefinition`` instances into OpenAI ``ChatCompletionToolParam`` dicts."""

    @staticmethod
    def to_openai(tools: Optional[List[ToolDefinition]]) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        return [OpenAIToolsConverter._convert(t) for t in tools]

    @staticmethod
    def _convert(tool: ToolDefinition) -> ChatCompletionToolParam:
        function: FunctionDefinition = {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        return ChatCompletionToolParam(type="function", function=function)
