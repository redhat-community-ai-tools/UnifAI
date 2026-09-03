"""
Converter from ``ToolDefinition`` to OpenAI-native tool definitions.

Uses the SDK's own ``ChatCompletionToolParam`` and ``FunctionDefinition``
TypedDicts so the output is type-checked against the API spec — misspelled
keys or wrong value types are caught by the type checker, not at runtime.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from openai.types.chat import ChatCompletionToolParam
from openai.types.shared_params import FunctionDefinition

from ...tools.common.tool_definition import ToolDefinition


class OpenAIToolsConverter:
    """Converts ``ToolDefinition`` instances into OpenAI ``ChatCompletionToolParam`` dicts."""

    @staticmethod
    def to_openai(
        tools: Optional[List[ToolDefinition]],
        name_map: Optional[Dict[str, str]] = None,
    ) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        return [OpenAIToolsConverter._convert(t, name_map) for t in tools]

    @staticmethod
    def _convert(
        tool: ToolDefinition,
        name_map: Optional[Dict[str, str]] = None,
    ) -> ChatCompletionToolParam:
        function: FunctionDefinition = {
            "name": name_map.get(tool.name, tool.name) if name_map else tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
        }
        return ChatCompletionToolParam(type="function", function=function)
