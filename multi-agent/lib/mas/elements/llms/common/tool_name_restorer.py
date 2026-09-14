"""
Shared helper for restoring sanitized tool names on inbound LLM messages.

Both the OpenAI Responses API provider and the OpenAI-compatible (Chat
Completions) provider sanitize tool names before sending them to the
external API and need to map them back on the way in.
"""

from __future__ import annotations

from typing import Dict

from mas.elements.llms.common.chat.message import ChatMessage
from mas.elements.llms.common.name_sanitizer import map_name


def restore_tool_names(rev_names: Dict[str, str], msg: ChatMessage) -> ChatMessage:
    """Map provider-safe names back to domain names on an inbound message.

    Args:
        rev_names: Reverse mapping from provider-safe name → original domain name.
        msg: The inbound ``ChatMessage`` whose tool_call names to restore.

    Returns the message unchanged when it carries no tool calls.
    """
    if not msg.tool_calls:
        return msg
    restored = [
        tc.model_copy(update={"name": map_name(tc.name, rev_names)})
        for tc in msg.tool_calls
    ]
    return msg.model_copy(update={"tool_calls": restored})
