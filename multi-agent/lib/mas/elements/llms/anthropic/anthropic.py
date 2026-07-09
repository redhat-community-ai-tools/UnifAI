"""
Anthropic (Claude) LLM implementation using the native ``anthropic`` Python SDK.

Talks to the Anthropic Messages API. System prompts are passed via the
top-level ``system`` parameter and tool calls are modelled as ``tool_use`` /
``tool_result`` content blocks (see ``AnthropicMessageConverter``).
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterator, List, Optional, Union

from anthropic import Anthropic

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import AnthropicMessageConverter
from .tools_converter import AnthropicToolsConverter


class AnthropicLLM(BaseLLM):
    """LLM client backed by the native Anthropic Python SDK.

    Responsibilities are split across dedicated collaborators:

    * **AnthropicMessageConverter** – bidirectional ``ChatMessage`` ↔ Anthropic messages
    * **AnthropicToolsConverter** – ``ToolDefinition`` → Anthropic tool schema
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        **extra: Any,
    ) -> None:
        self._name = "anthropic"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._top_p = top_p
        self._top_k = top_k
        self._tools: Optional[List[Dict[str, Any]]] = None
        self._client = Anthropic(api_key=api_key, **extra)

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        request = self._build_request(messages)
        response = self._client.messages.create(**request)
        return AnthropicMessageConverter.from_anthropic(response)

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        request = self._build_request(messages, **call_params)
        accumulated_content = ""

        with self._client.messages.stream(**request) as stream:
            for text in stream.text_stream:
                accumulated_content += text
                yield text

            final_message = stream.get_final_message()

        tool_message = AnthropicMessageConverter.message_from_blocks(
            getattr(final_message, "content", None) or []
        )
        if tool_message.tool_calls:
            yield ChatMessage(
                role=Role.ASSISTANT,
                content=accumulated_content,
                tool_calls=tool_message.tool_calls,
            )

    def bind_tools(self, tools: List[ToolDefinition]) -> AnthropicLLM:
        clone = copy.copy(self)
        clone._tools = AnthropicToolsConverter.to_anthropic(tools)
        return clone

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_request(
        self,
        messages: List[ChatMessage],
        **overrides: Any,
    ) -> Dict[str, Any]:
        """Assemble the kwargs dict for ``messages.create`` / ``messages.stream``."""
        split = AnthropicMessageConverter.to_anthropic(messages)

        request: Dict[str, Any] = {
            "model": self._model,
            "messages": split.messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
        }

        if split.system:
            request["system"] = split.system
        if self._top_p is not None:
            request["top_p"] = self._top_p
        if self._top_k is not None:
            request["top_k"] = self._top_k
        if self._tools:
            request["tools"] = self._tools
        if overrides:
            request.update(overrides)

        return request
