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
from ..common.name_sanitizer import build_name_maps
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
    inbound tool calls.  All mapping logic lives in this class.
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
            )
            result_msg = self._restore_tool_names(result_msg)
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
                    tc.model_copy(
                        update={"name": self._rev_names.get(tc.name, tc.name)},
                    )
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
        clone._tools = OpenAIToolsConverter.to_openai(tools)
        if clone._tools:
            for tool_param, tool_def in zip(clone._tools, tools):
                tool_param["function"]["name"] = clone._fwd_names[tool_def.name]
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
        raw_messages = OpenAIMessageConverter.to_openai(messages)
        self._sanitize_outbound_names(raw_messages)
        request: Dict[str, Any] = {
            "model": self._model,
            "messages": raw_messages,
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

    def _sanitize_outbound_names(self, messages: List[Dict[str, Any]]) -> None:
        """Replace domain tool names with provider-safe names in message dicts."""
        if not self._fwd_names:
            return
        for msg in messages:
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                original = fn.get("name")
                if original in self._fwd_names:
                    fn["name"] = self._fwd_names[original]

    def _restore_tool_names(self, msg: ChatMessage) -> ChatMessage:
        """Map provider-safe tool names back to domain names."""
        if not msg.tool_calls or not self._rev_names:
            return msg
        restored = [
            tc.model_copy(
                update={"name": self._rev_names.get(tc.name, tc.name)},
            )
            for tc in msg.tool_calls
        ]
        return msg.model_copy(update={"tool_calls": restored})
