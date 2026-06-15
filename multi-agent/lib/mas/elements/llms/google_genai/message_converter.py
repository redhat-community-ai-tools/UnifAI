"""
Bidirectional converter between domain ChatMessage and Google GenAI types.

Google GenAI uses a different message model from OpenAI:
  - System instructions are passed via ``GenerateContentConfig.system_instruction``,
    not as a content message.
  - Content roles are ``'user'`` and ``'model'`` (not ``'assistant'``).
  - Tool results are ``'user'``-role messages with ``Part.from_function_response()``.
  - Tool calls are ``'model'``-role messages with ``Part.from_function_call()``.

**Thought-signature preservation**: Gemini models attach ``thought_signature``
bytes to ``Part`` objects (especially function-call parts) that must be echoed
back verbatim in subsequent requests.  This converter stores the original
``types.Part`` list in ``ChatMessage.additional_kwargs["_genai_parts"]`` so that
``_assistant_to_content`` can replay them with signatures intact.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

from google.genai import types

from ..common.chat.message import ChatMessage, Role, ToolCall


@dataclass(frozen=True)
class SplitMessages:
    """Result of splitting domain messages for the Google GenAI API.

    Google GenAI requires system instructions to be passed separately
    from conversation content.
    """
    system_instruction: Optional[str]
    contents: List[types.Content]


class GoogleGenAIMessageConverter:
    """Stateless converter between ``ChatMessage`` and native Google GenAI types."""

    # ------------------------------------------------------------------
    # Domain → Google GenAI
    # ------------------------------------------------------------------

    @staticmethod
    def to_genai(messages: List[ChatMessage]) -> SplitMessages:
        """Convert domain messages to Google GenAI format.

        Returns a ``SplitMessages`` with the system instruction extracted
        separately (as Google GenAI requires) and the remaining conversation
        as ``types.Content`` objects.
        """
        system_parts: List[str] = []
        contents: List[types.Content] = []
        tool_call_names = GoogleGenAIMessageConverter._build_tool_call_name_map(messages)

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_parts.append(msg.content)
            elif msg.role == Role.USER:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=msg.content)],
                ))
            elif msg.role == Role.ASSISTANT:
                contents.append(GoogleGenAIMessageConverter._assistant_to_content(msg))
            elif msg.role == Role.TOOL:
                contents.append(GoogleGenAIMessageConverter._tool_result_to_content(
                    msg, tool_call_names,
                ))

        return SplitMessages(
            system_instruction="\n".join(system_parts) if system_parts else None,
            contents=contents,
        )

    # ------------------------------------------------------------------
    # Google GenAI → Domain
    # ------------------------------------------------------------------

    @staticmethod
    def from_genai(response: types.GenerateContentResponse) -> ChatMessage:
        """Convert a Google GenAI response to a domain ChatMessage.

        Original ``Part`` objects are preserved in ``additional_kwargs``
        so that ``thought_signature`` and other opaque fields survive
        the domain round-trip.
        """
        raw_parts: List[types.Part] = list(response.parts or [])
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for part in raw_parts:
            if part.text is not None and not part.thought:
                text_parts.append(part.text)
            elif part.function_call is not None:
                tool_calls.append(GoogleGenAIMessageConverter._parse_function_call(
                    part.function_call,
                ))

        return ChatMessage(
            role=Role.ASSISTANT,
            content="".join(text_parts),
            tool_calls=tool_calls or None,
            additional_kwargs={"_genai_parts": raw_parts},
        )

    @staticmethod
    def from_genai_parts(
        parts: List[types.Part],
        accumulated_text: str = "",
    ) -> ChatMessage:
        """Build a domain ChatMessage from collected streaming parts.

        Accepts the full ``Part`` objects (not just ``FunctionCall``) so
        that ``thought_signature`` is preserved for the round-trip.
        """
        tool_calls = [
            GoogleGenAIMessageConverter._parse_function_call(p.function_call)
            for p in parts
            if p.function_call is not None
        ]

        all_parts = list(parts)
        if accumulated_text:
            all_parts.insert(0, types.Part.from_text(text=accumulated_text))

        return ChatMessage(
            role=Role.ASSISTANT,
            content=accumulated_text,
            tool_calls=tool_calls or None,
            additional_kwargs={"_genai_parts": all_parts},
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assistant_to_content(msg: ChatMessage) -> types.Content:
        """Convert an assistant message (with optional tool calls) to model Content.

        If the message carries preserved ``_genai_parts`` (set by
        ``from_genai`` / ``from_genai_parts``), those are replayed verbatim
        so that ``thought_signature`` and other opaque fields are retained.
        """
        preserved = (msg.additional_kwargs or {}).get("_genai_parts")
        if preserved is not None:
            return types.Content(role="model", parts=preserved)

        parts: List[types.Part] = []

        if msg.content:
            parts.append(types.Part.from_text(text=msg.content))

        for tc in (msg.tool_calls or []):
            parts.append(types.Part.from_function_call(
                name=tc.name,
                args=tc.args,
            ))

        return types.Content(role="model", parts=parts or [types.Part.from_text(text="")])

    @staticmethod
    def _tool_result_to_content(
        msg: ChatMessage,
        tool_call_names: Dict[str, str],
    ) -> types.Content:
        """Convert a tool-result message to a user Content with function_response."""
        func_name = tool_call_names.get(msg.tool_call_id or "", "unknown")

        response_data = GoogleGenAIMessageConverter._parse_tool_content(msg.content)

        return types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name=func_name,
                response=response_data,
            )],
        )

    @staticmethod
    def _parse_tool_content(content: str) -> Dict[str, Any]:
        """Parse tool result content into a dict suitable for function_response."""
        try:
            parsed = json.loads(content)
            return parsed if isinstance(parsed, dict) else {"result": parsed}
        except (json.JSONDecodeError, TypeError):
            return {"result": content}

    @staticmethod
    def _parse_function_call(fc: types.FunctionCall) -> ToolCall:
        return ToolCall(
            name=fc.name or "",
            args=fc.args or {},
            tool_call_id=fc.id or f"tool-{uuid4()}",
        )

    @staticmethod
    def _build_tool_call_name_map(messages: List[ChatMessage]) -> Dict[str, str]:
        """Build a mapping of tool_call_id → function_name from assistant messages.

        Google GenAI's ``Part.from_function_response`` requires the function
        name, which our domain ``Role.TOOL`` messages don't carry directly.
        We reconstruct it from the preceding assistant tool_calls.
        """
        name_map: Dict[str, str] = {}
        for msg in messages:
            if msg.role == Role.ASSISTANT and msg.tool_calls:
                for tc in msg.tool_calls:
                    name_map[tc.tool_call_id] = tc.name
        return name_map
