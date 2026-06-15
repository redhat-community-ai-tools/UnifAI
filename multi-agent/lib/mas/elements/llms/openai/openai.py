"""
OpenAI LLM implementation using the native ``openai`` Python SDK.

Supports any OpenAI-compatible API (OpenAI, vLLM, Azure, etc.) via
the ``base_url`` parameter.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionToolParam

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import OpenAIMessageConverter
from .tools_converter import OpenAIToolsConverter
from .stream_aggregator import StreamToolCallAggregator

logger = logging.getLogger(__name__)


class OpenAILLM(BaseLLM):
    """LLM client backed by the native OpenAI Python SDK.

    Responsibilities are split across dedicated collaborators:

    * **OpenAIMessageConverter** – bidirectional ``ChatMessage`` ↔ OpenAI dict
    * **OpenAIToolsConverter** – ``BaseTool`` → OpenAI function-tool schema
    * **StreamToolCallAggregator** – reassembles incremental tool-call deltas
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        api_key: str = "EMPTY",
        **extra: Any,
    ) -> None:
        self._name = "openai"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._tools: Optional[List[ChatCompletionToolParam]] = None
        self._client = OpenAI(api_key=api_key, base_url=base_url, **extra)

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        request = self._build_request(messages)
        response = self._client.chat.completions.create(**request)
        return OpenAIMessageConverter.from_openai(response.choices[0].message)

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        request = self._build_request(messages, stream=True, **call_params)
        aggregator = StreamToolCallAggregator()
        accumulated_content = ""
        yielded = False

        for chunk in self._client.chat.completions.create(**request):
            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta.content:
                accumulated_content += delta.content
                yield delta.content
                yielded = True

            if delta.tool_calls:
                aggregator.absorb(delta.tool_calls)

        if aggregator.has_tool_calls:
            yield ChatMessage(
                role=Role.ASSISTANT,
                content=accumulated_content,
                tool_calls=aggregator.build(),
            )
            yielded = True

        if not yielded:
            logger.warning("OpenAI stream returned no content and no tool calls (model=%s)", self._model)
            yield ""

    def bind_tools(self, tools: List[ToolDefinition]) -> OpenAILLM:
        clone = copy.copy(self)
        clone._tools = OpenAIToolsConverter.to_openai(tools)
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
        *,
        stream: bool = False,
        **overrides: Any,
    ) -> Dict[str, Any]:
        """Assemble the kwargs dict for ``chat.completions.create``."""
        request: Dict[str, Any] = {
            "model": self._model,
            "messages": OpenAIMessageConverter.to_openai(messages),
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if stream:
            request["stream"] = True
        if self._tools:
            request["tools"] = self._tools
        if overrides:
            request.update(overrides)
        return request
