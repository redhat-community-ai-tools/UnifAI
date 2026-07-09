"""
Bidirectional converter between domain ChatMessage and Anthropic Messages API.

The Anthropic Messages API differs from OpenAI chat-completions:
  - System prompts are passed via the top-level ``system`` parameter, not as a
    message with a ``system`` role.
  - Only ``'user'`` and ``'assistant'`` roles exist, and roles must alternate,
    so consecutive same-role messages are coalesced into one.
  - Assistant tool calls are ``tool_use`` content blocks
    (``{"type": "tool_use", "id", "name", "input"}``).
  - Tool results are ``'user'``-role messages carrying ``tool_result`` blocks
    (``{"type": "tool_result", "tool_use_id", "content"}``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..common.chat.message import ChatMessage, Role, ToolCall


@dataclass(frozen=True)
class SplitMessages:
    """Result of splitting domain messages for the Anthropic Messages API.

    Anthropic requires the system prompt to be passed separately from the
    conversation content.
    """
    system: Optional[str]
    messages: List[Dict[str, Any]]


class AnthropicMessageConverter:
    """Stateless converter between ``ChatMessage`` and Anthropic message dicts."""

    # ------------------------------------------------------------------
    # Domain → Anthropic
    # ------------------------------------------------------------------

    @staticmethod
    def to_anthropic(messages: List[ChatMessage]) -> SplitMessages:
        """Convert domain messages to Anthropic format.

        Returns a ``SplitMessages`` with the system prompt extracted separately
        and the remaining conversation as Anthropic message dicts with
        alternating roles.
        """
        system_parts: List[str] = []
        raw: List[Dict[str, Any]] = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                if msg.content:
                    system_parts.append(msg.content)
            elif msg.role == Role.USER:
                raw.append({
                    "role": "user",
                    "content": [AnthropicMessageConverter._text_block(msg.content)],
                })
            elif msg.role == Role.ASSISTANT:
                raw.append({
                    "role": "assistant",
                    "content": AnthropicMessageConverter._assistant_blocks(msg),
                })
            elif msg.role == Role.TOOL:
                raw.append({
                    "role": "user",
                    "content": [AnthropicMessageConverter._tool_result_block(msg)],
                })

        return SplitMessages(
            system="\n".join(system_parts) if system_parts else None,
            messages=AnthropicMessageConverter._coalesce(raw),
        )

    # ------------------------------------------------------------------
    # Anthropic → Domain
    # ------------------------------------------------------------------

    @staticmethod
    def from_anthropic(response: Any) -> ChatMessage:
        """Convert an Anthropic ``Message`` response to a domain ChatMessage."""
        return AnthropicMessageConverter.message_from_blocks(
            getattr(response, "content", None) or []
        )

    @staticmethod
    def message_from_blocks(blocks: List[Any]) -> ChatMessage:
        """Build a domain ChatMessage from Anthropic content blocks.

        Accepts the block objects returned by the SDK (``text`` and
        ``tool_use`` blocks) and folds them into a single assistant message.
        """
        text_parts: List[str] = []
        tool_calls: List[ToolCall] = []

        for block in blocks:
            block_type = getattr(block, "type", None)
            if block_type == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif block_type == "tool_use":
                tool_calls.append(ToolCall(
                    name=getattr(block, "name", "") or "",
                    args=dict(getattr(block, "input", None) or {}),
                    tool_call_id=getattr(block, "id", "") or "",
                ))

        return ChatMessage(
            role=Role.ASSISTANT,
            content="".join(text_parts),
            tool_calls=tool_calls or None,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _text_block(text: str) -> Dict[str, Any]:
        return {"type": "text", "text": text or ""}

    @staticmethod
    def _assistant_blocks(msg: ChatMessage) -> List[Dict[str, Any]]:
        """Convert an assistant message (with optional tool calls) to blocks."""
        blocks: List[Dict[str, Any]] = []

        if msg.content:
            blocks.append(AnthropicMessageConverter._text_block(msg.content))

        for tc in (msg.tool_calls or []):
            blocks.append({
                "type": "tool_use",
                "id": tc.tool_call_id,
                "name": tc.name,
                "input": tc.args,
            })

        # An assistant turn must carry at least one content block.
        if not blocks:
            blocks.append(AnthropicMessageConverter._text_block(""))

        return blocks

    @staticmethod
    def _tool_result_block(msg: ChatMessage) -> Dict[str, Any]:
        """Convert a tool-result message to a ``tool_result`` content block."""
        return {
            "type": "tool_result",
            "tool_use_id": msg.tool_call_id or "",
            "content": msg.content,
        }

    @staticmethod
    def _coalesce(raw: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge adjacent same-role messages so roles strictly alternate.

        Anthropic rejects consecutive messages with the same role (e.g. two
        user-role tool results in a row), so their content blocks are merged.
        """
        merged: List[Dict[str, Any]] = []
        for entry in raw:
            if merged and merged[-1]["role"] == entry["role"]:
                merged[-1]["content"].extend(entry["content"])
            else:
                merged.append({"role": entry["role"], "content": list(entry["content"])})
        return merged
