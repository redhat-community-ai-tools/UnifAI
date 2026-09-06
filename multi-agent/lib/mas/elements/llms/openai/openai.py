"""
OpenAI LLM implementation using the native ``openai`` Python SDK.

Supports any OpenAI-compatible API (OpenAI, vLLM, Azure, etc.) via
the ``base_url`` parameter.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionToolParam

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ..common.name_sanitizer import build_name_maps, map_name
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import OpenAIMessageConverter
from .tools_converter import OpenAIToolsConverter
from .stream_aggregator import StreamToolCallAggregator
from mas.core.tracing import TracingService


class OpenAILLM(BaseLLM):
    """LLM client backed by the native OpenAI Python SDK.

    Responsibilities are split across dedicated collaborators:

    * **OpenAIMessageConverter** – bidirectional ``ChatMessage`` ↔ OpenAI dict
    * **OpenAIToolsConverter** – ``BaseTool`` → OpenAI function-tool schema
    * **StreamToolCallAggregator** – reassembles incremental tool-call deltas

    Tool names containing dots (e.g. ``time.get_current_time``) are
    sanitized to underscores at the API boundary and restored on
    inbound tool calls.  Name maps are built in ``bind_tools`` and
    passed through to the converters.
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        api_key: str = "EMPTY",
        tracing: TracingService = None,
        **extra: Any,
    ) -> None:
        self._name = "openai"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._tools: Optional[List[ChatCompletionToolParam]] = None
        self._fwd_names: Dict[str, str] = {}  # domain → provider-safe
        self._rev_names: Dict[str, str] = {}  # provider-safe → domain
        self._client = OpenAI(api_key=api_key, base_url=base_url, **extra)
        self._tracing = tracing

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        request = self._build_request(messages)
        with self._tracing.trace_llm(
            model=self._model,
            provider="openai",
            input_messages=[{"role": m.role.value, "content": m.content} for m in messages[-5:]],
        ) as gen:
            try:
                response = self._client.chat.completions.create(**request)
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            result_msg = OpenAIMessageConverter.from_openai(
                response.choices[0].message,
                rev_names=self._rev_names,
            )
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            gen.update(output=result_msg.content, usage_details=usage or None)
        return result_msg

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        request = self._build_request(messages, stream=True, **call_params)
        aggregator = StreamToolCallAggregator()
        accumulated_content = ""

        with self._tracing.trace_llm(
            model=self._model,
            provider="openai",
            input_messages=[{"role": m.role.value, "content": m.content} for m in messages[-5:]],
            metadata={"streaming": True},
        ) as gen:
            try:
                stream_iter = self._client.chat.completions.create(**request)
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            for chunk in stream_iter:
                if not chunk.choices:
                    if hasattr(chunk, "usage") and chunk.usage:
                        gen.update(usage_details={
                            "input_tokens": chunk.usage.prompt_tokens,
                            "output_tokens": chunk.usage.completion_tokens,
                            "total_tokens": chunk.usage.total_tokens,
                        })
                    continue

                delta = chunk.choices[0].delta

                if delta.content:
                    accumulated_content += delta.content
                    yield delta.content

                if delta.tool_calls:
                    aggregator.absorb(delta.tool_calls)

            gen.update(output=accumulated_content)

        if aggregator.has_tool_calls:
            tool_calls = aggregator.build()
            if tool_calls:
                tool_calls = [
                    tc.model_copy(update={"name": map_name(tc.name, self._rev_names)})
                    for tc in tool_calls
                ]
            yield ChatMessage(
                role=Role.ASSISTANT,
                content=accumulated_content,
                tool_calls=tool_calls,
            )

    def bind_tools(self, tools: List[ToolDefinition]) -> OpenAILLM:
        clone = copy.copy(self)
        clone._fwd_names, clone._rev_names = build_name_maps(
            t.name for t in tools
        )
        clone._tools = OpenAIToolsConverter.to_openai(tools, clone._fwd_names)
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
            "messages": OpenAIMessageConverter.to_openai(
                messages, name_map=self._fwd_names,
            ),
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
