import json
from typing import Any, List, Union

from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from mas.elements.llms.common.chat.message import ChatMessage, Role, ToolCall
from .utils import ensure_tool_call_id


def normalise_content(content: Union[str, list, Any]) -> str:
    """Normalise LangChain message content to a plain string.

    LangChain messages may carry ``content`` as:
      - ``str``  — pass through
      - ``list`` — list of content blocks, e.g. ``[{'type': 'text', 'text': '…'}]``
                    or plain strings; extract and join the text parts
      - other    — fallback to ``str()``

    This is common when Deep Agents middleware or multi-modal providers
    assemble compound system / assistant messages.
    """
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts: List[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)

    return str(content)


class LangChainConverter:
    """Bidirectional converter between domain ``ChatMessage`` and LangChain messages."""

    # ------------------------------------------------------------------
    # Domain → LangChain
    # ------------------------------------------------------------------

    @staticmethod
    def to_lc(history: List[ChatMessage]) -> List[BaseMessage]:
        return [LangChainConverter.to_lc_message(m) for m in history]

    @staticmethod
    def to_lc_message(m: ChatMessage) -> BaseMessage:
        """Convert a single domain message to its LangChain equivalent."""
        if m.role == Role.SYSTEM:
            return SystemMessage(content=m.content)

        if m.role == Role.USER:
            return HumanMessage(content=m.content)

        if m.role == Role.ASSISTANT:
            return LangChainConverter._assistant_to_ai_message(m)

        if m.role == Role.TOOL:
            tool_name = getattr(m, "name", None) or "unknown_tool"
            return ToolMessage(content=m.content, tool_call_id=m.tool_call_id, name=tool_name)

        raise ValueError(f"Unknown role {m.role}")

    @staticmethod
    def to_lc_message_chunk(m: ChatMessage) -> AIMessageChunk:
        """Convert a domain assistant message to an ``AIMessageChunk``.

        Populates both ``tool_calls`` (final form) and ``tool_call_chunks``
        (needed by LangChain's streaming aggregation via the ``+`` operator).

        ``additional_kwargs`` are forwarded so that provider-specific
        metadata (e.g. Google GenAI's ``_genai_parts`` carrying
        ``thought_signature``) survives LangChain's chunk aggregation.
        """
        tool_calls, tool_call_chunks = LangChainConverter._build_tool_call_pairs(m)
        return AIMessageChunk(
            content=m.content,
            tool_calls=tool_calls,
            tool_call_chunks=tool_call_chunks,
            additional_kwargs=m.additional_kwargs or {},
        )

    # ------------------------------------------------------------------
    # LangChain → Domain
    # ------------------------------------------------------------------

    @staticmethod
    def from_lc(lc_msgs: List[BaseMessage]) -> List[ChatMessage]:
        return [LangChainConverter.from_lc_message(m) for m in lc_msgs]

    @staticmethod
    def from_lc_message(m: BaseMessage) -> ChatMessage:
        text = normalise_content(m.content)

        if isinstance(m, SystemMessage):
            return ChatMessage(role=Role.SYSTEM, content=text)

        if isinstance(m, HumanMessage):
            return ChatMessage(role=Role.USER, content=text)

        if isinstance(m, AIMessage):
            tool_calls = None

            if getattr(m, "tool_call_chunks", None) and m.type == "tool_call_chunk":
                tool_calls = [ensure_tool_call_id(tc) for tc in m.tool_call_chunks]
            elif getattr(m, "tool_calls", None):
                tool_calls = [ensure_tool_call_id(tc) for tc in m.tool_calls]

            return ChatMessage(
                role=Role.ASSISTANT,
                content=text or " " if tool_calls else text,
                tool_calls=[ToolCall(**tc.model_dump()) for tc in tool_calls] if tool_calls else None,
                additional_kwargs=getattr(m, "additional_kwargs", None),
            )

        if isinstance(m, ToolMessage):
            return ChatMessage(role=Role.TOOL, content=text, tool_call_id=m.tool_call_id)

        raise ValueError(f"Unknown message type: {type(m)}")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _assistant_to_ai_message(m: ChatMessage) -> AIMessage:
        kwargs = m.additional_kwargs or {}

        if not m.tool_calls:
            return AIMessage(content=m.content, additional_kwargs=kwargs)

        tool_calls = [
            {"name": tc.name, "args": tc.args, "id": tc.tool_call_id, "type": "tool_call"}
            for tc in m.tool_calls
        ]
        return AIMessage(
            content=m.content if m.content else "[TOOL CALL]",
            tool_calls=tool_calls,
            additional_kwargs=kwargs,
        )

    @staticmethod
    def _build_tool_call_pairs(m: ChatMessage) -> tuple[list, list]:
        """Build both ``tool_calls`` and ``tool_call_chunks`` lists from domain tool calls."""
        tool_calls = []
        tool_call_chunks = []
        for i, tc in enumerate(m.tool_calls or []):
            tool_calls.append(
                {"name": tc.name, "args": tc.args, "id": tc.tool_call_id, "type": "tool_call"}
            )
            tool_call_chunks.append(
                {"name": tc.name, "args": json.dumps(tc.args), "id": tc.tool_call_id, "index": i, "type": "tool_call_chunk"}
            )
        return tool_calls, tool_call_chunks
