"""
Converter from ``ToolDefinition`` to Anthropic-native tool definitions.

Anthropic tools are plain dicts of the shape::

    {"name": ..., "description": ..., "input_schema": {<JSON Schema>}}

where ``input_schema`` is a JSON Schema object describing the tool parameters.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ...tools.common.tool_definition import ToolDefinition


def _empty_input_schema() -> Dict[str, Any]:
    """Return a fresh, unshared empty JSON Schema object."""
    return {"type": "object", "properties": {}}


class AnthropicToolsConverter:
    """Converts ``ToolDefinition`` instances into Anthropic tool dicts."""

    @staticmethod
    def to_anthropic(
        tools: Optional[List[ToolDefinition]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert tool definitions to Anthropic format.

        Returns a list of Anthropic tool dicts, or *None* if no tools are
        provided.
        """
        if not tools:
            return None

        return [AnthropicToolsConverter._to_tool(t) for t in tools]

    @staticmethod
    def _to_tool(tool: ToolDefinition) -> Dict[str, Any]:
        """Convert a single ToolDefinition to an Anthropic tool dict."""
        return {
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.parameters or _empty_input_schema(),
        }
