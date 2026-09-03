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
from .name_sanitizer import ToolNameSanitizer


class OpenAIToolsConverter:
    """Converts ``ToolDefinition`` instances into OpenAI ``ChatCompletionToolParam`` dicts.

    Function names are sanitized to ``^[a-zA-Z0-9_-]+$`` (OpenAI rejects
    dots).  Domain ``ToolDefinition.name`` is left unchanged; callers
    pass the same ``ToolNameSanitizer`` into the message converter so
    inbound tool calls map back to the original name.
    """

    @staticmethod
    def to_openai(
        tools: Optional[List[ToolDefinition]],
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> Optional[List[ChatCompletionToolParam]]:
        if not tools:
            return None
        sanitizer = sanitizer or ToolNameSanitizer(t.name for t in tools)
        return [OpenAIToolsConverter._convert(t, sanitizer) for t in tools]

    @staticmethod
    def _convert(
        tool: ToolDefinition,
        sanitizer: ToolNameSanitizer,
    ) -> ChatCompletionToolParam:
        function: FunctionDefinition = {
            "name": sanitizer.to_provider(tool.name),
            "description": tool.description,
            "parameters": tool.parameters,
        }
        return ChatCompletionToolParam(type="function", function=function)
