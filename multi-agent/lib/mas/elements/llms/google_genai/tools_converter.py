"""
Converter from ``ToolDefinition`` to Google GenAI-native tool definitions.

Uses the SDK's ``types.FunctionDeclaration`` and ``types.Tool`` Pydantic models
so the output is validated against the API spec at construction time.

Google GenAI has stricter schema validation than other providers, so
``SchemaSanitizer`` is applied to remove patterns that would be rejected
(empty properties, title-only fields, etc.).
"""

from __future__ import annotations

from typing import List, Optional

from google.genai import types

from ...tools.common.tool_definition import ToolDefinition
from .schema_sanitizer import SchemaSanitizer


class GoogleGenAIToolsConverter:
    """Converts ``ToolDefinition`` instances into a Google GenAI ``types.Tool``."""

    @staticmethod
    def to_genai(tools: Optional[List[ToolDefinition]]) -> Optional[List[types.Tool]]:
        """Convert tool definitions to Google GenAI format.

        Returns a list containing a single ``types.Tool`` with all function
        declarations, or *None* if no tools are provided.
        """
        if not tools:
            return None

        declarations = [GoogleGenAIToolsConverter._to_declaration(t) for t in tools]
        return [types.Tool(function_declarations=declarations)]

    @staticmethod
    def _to_declaration(tool: ToolDefinition) -> types.FunctionDeclaration:
        """Convert a single ToolDefinition to a ``FunctionDeclaration``."""
        parameters = SchemaSanitizer.sanitize(tool.parameters)

        return types.FunctionDeclaration(
            name=tool.name,
            description=tool.description,
            parameters_json_schema=parameters,
        )
