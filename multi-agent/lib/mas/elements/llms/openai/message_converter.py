"""
Bidirectional converter between domain ChatMessage and OpenAI API messages.

Handles all message roles (system, user, assistant, tool) including
assistant messages with tool_calls and tool result messages.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from uuid import uuid4

from ..common.chat.message import ChatMessage, Role, ToolCall
from ..common.name_sanitizer import ToolNameSanitizer

_ROLE_MAP: Dict[Role, str] = {
    Role.SYSTEM: "system",
    Role.USER: "user",
    Role.ASSISTANT: "assistant",
    Role.TOOL: "tool",
}


class OpenAIMessageConverter:
    """Stateless converter between ``ChatMessage`` and native OpenAI message dicts."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @staticmethod
    def to_openai(
        messages: List[ChatMessage],
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> List[Dict[str, Any]]:
        """Convert a list of domain messages to OpenAI API dicts."""
        return [OpenAIMessageConverter._to_dict(m, sanitizer) for m in messages]

    @staticmethod
    def from_openai(
        msg: Any,
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> ChatMessage:
        """Convert an OpenAI ``ChatCompletionMessage`` to a domain ChatMessage."""
        tool_calls = OpenAIMessageConverter._parse_tool_calls(
            getattr(msg, "tool_calls", None),
            sanitizer,
        )
        return ChatMessage(
            role=Role.ASSISTANT,
            content=msg.content or "",
            tool_calls=tool_calls,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _to_dict(
        m: ChatMessage,
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> Dict[str, Any]:
        role = _ROLE_MAP.get(m.role)
        if role is None:
            raise ValueError(f"Unknown role: {m.role}")

        if m.role in (Role.SYSTEM, Role.USER):
            return {"role": role, "content": m.content}

        if m.role == Role.ASSISTANT:
            d: Dict[str, Any] = {"role": role, "content": m.content or ""}
            if m.tool_calls:
                d["tool_calls"] = [
                    OpenAIMessageConverter._tool_call_to_dict(tc, sanitizer)
                    for tc in m.tool_calls
                ]
            return d

        # Role.TOOL
        return {
            "role": role,
            "content": m.content,
            "tool_call_id": m.tool_call_id,
        }

    @staticmethod
    def _tool_call_to_dict(
        tc: ToolCall,
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> Dict[str, Any]:
        name = sanitizer.to_provider(tc.name) if sanitizer is not None else tc.name
        return {
            "id": tc.tool_call_id,
            "type": "function",
            "function": {
                "name": name,
                "arguments": json.dumps(tc.args),
            },
        }

    @staticmethod
    def _parse_tool_calls(
        raw: Optional[List[Any]],
        sanitizer: Optional[ToolNameSanitizer] = None,
    ) -> Optional[List[ToolCall]]:
        if not raw:
            return None
        result = [
            ToolCall(
                name=(
                    sanitizer.to_domain(tc.function.name)
                    if sanitizer is not None
                    else tc.function.name
                ),
                args=(
                    json.loads(tc.function.arguments)
                    if isinstance(tc.function.arguments, str)
                    else tc.function.arguments
                ),
                tool_call_id=tc.id or f"tool-{uuid4()}",
            )
            for tc in raw
        ]
        return result or None
