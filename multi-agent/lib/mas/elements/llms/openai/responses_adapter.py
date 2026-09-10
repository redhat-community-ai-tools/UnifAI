"""
Adapter between domain ChatMessage objects and the OpenAI Responses API format.

The Responses API uses a flat list of typed items instead of the
role-based message array used by Chat Completions.

Key format differences handled here:

  - System messages → ``{"type": "message", "role": "developer", ...}``
  - User messages → ``{"type": "message", "role": "user", ...}``
  - Assistant text → ``{"type": "message", "role": "assistant", ...}``
  - Tool calls from LLM → ``{"type": "function_call", "name": ..., "call_id": ...}``
  - Tool results → ``{"type": "function_call_output", "call_id": ..., "output": ...}``
  - Tool definitions → ``{"type": "function", "name": ..., "parameters": ...}``
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..common.chat.message import ChatMessage, Role, ToolCall
from ..common.name_sanitizer import map_name
from ...tools.common.tool_definition import ToolDefinition


class ResponsesAdapter:
    """Stateless adapter for the OpenAI Responses API wire format."""

    # ------------------------------------------------------------------
    # Domain → Responses API
    # ------------------------------------------------------------------

    @staticmethod
    def to_input(
        messages: List[ChatMessage],
        fwd_names: Optional[Dict[str, str]] = None,
    ) -> List[Dict[str, Any]]:
        """Convert domain messages to Responses API ``input`` items.

        If *fwd_names* is provided, tool-call names in assistant messages
        are sanitized for the provider.
        """
        items: List[Dict[str, Any]] = []
        for m in messages:
            if m.role in (Role.SYSTEM, Role.USER):
                items.append({
                    "type": "message",
                    "role": "user" if m.role == Role.USER else "developer",
                    "content": m.content,
                })
            elif m.role == Role.ASSISTANT:
                if m.content:
                    items.append({
                        "type": "message",
                        "role": "assistant",
                        "content": m.content,
                    })
                if m.tool_calls:
                    for tc in m.tool_calls:
                        name = map_name(tc.name, fwd_names) if fwd_names else tc.name
                        items.append({
                            "type": "function_call",
                            "name": name,
                            "arguments": json.dumps(tc.args),
                            "call_id": tc.tool_call_id,
                        })
            elif m.role == Role.TOOL:
                items.append({
                    "type": "function_call_output",
                    "call_id": m.tool_call_id or "",
                    "output": m.content,
                })
        return items

    @staticmethod
    def tools_to_responses(
        tools: Optional[List[ToolDefinition]],
    ) -> Optional[List[Dict[str, Any]]]:
        """Convert tool definitions to Responses API format."""
        if not tools:
            return None
        return [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
                "strict": False,
            }
            for t in tools
        ]

    # ------------------------------------------------------------------
    # Responses API → Domain
    # ------------------------------------------------------------------

    @staticmethod
    def from_response(response: Any) -> ChatMessage:
        """Extract a ChatMessage from a Responses API ``Response`` object.

        Iterates over ``response.output`` items, collecting text from
        ``message`` items and tool calls from ``function_call`` items.
        """
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for item in response.output:
            if item.type == "message":
                for content in item.content:
                    if hasattr(content, "text"):
                        text_parts.append(content.text)
            elif item.type == "function_call":
                tool_calls.append(
                    ToolCall(
                        name=item.name,
                        args=(
                            json.loads(item.arguments)
                            if isinstance(item.arguments, str)
                            else item.arguments
                        ),
                        tool_call_id=item.call_id or f"tool-{uuid4()}",
                    )
                )

        return ChatMessage(
            role=Role.ASSISTANT,
            content="".join(text_parts),
            tool_calls=tool_calls or None,
        )
