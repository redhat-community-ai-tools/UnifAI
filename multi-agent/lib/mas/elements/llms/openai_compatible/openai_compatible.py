"""
OpenAI-compatible LLM implementation using the Chat Completions API.

Works with any server implementing the ``/v1/chat/completions`` endpoint:
vLLM, LocalAI, Ollama, Azure OpenAI, and older OpenAI models (GPT-4, GPT-3.5).

For newer OpenAI models (GPT-5+) that require the Responses API, use the
``openai`` provider instead.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI
from openai.types.chat import ChatCompletionToolParam

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ..common.name_sanitizer import build_name_maps, map_name
from ..common.tool_name_restorer import restore_tool_names
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import OpenAIMessageConverter
from .tools_converter import OpenAIToolsConverter
from .stream_aggregator import (
    StreamMetadataCollector,
    StreamToolCallAggregator,
    build_response_metadata,
    extract_extra_fields,
)
from mas.core.tracing import TracingService


class OpenAICompatibleLLM(BaseLLM):
    """LLM client for any OpenAI-compatible Chat Completions API.

    Responsibilities are split across dedicated collaborators:

    * **OpenAIMessageConverter** – bidirectional ``ChatMessage`` ↔ OpenAI dict
    * **OpenAIToolsConverter** – ``ToolDefinition`` → Chat Completions tool schema
    * **StreamToolCallAggregator** – reassembles incremental tool-call deltas

    Tool names containing dots (e.g. ``time.get_current_time``) are
    sanitized to underscores at the API boundary and restored on
    inbound tool calls.  Converters remain unaware of sanitization.
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        api_key: str = "EMPTY",
        metadata_lookup_url: Optional[str] = None,
        tracing: TracingService = None,
        **extra: Any,
    ) -> None:
        self._name = "openai_compatible"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._tools: Optional[List[ChatCompletionToolParam]] = None
        self._fwd_names: Dict[str, str] = {}
        self._rev_names: Dict[str, str] = {}
        self._client = OpenAI(api_key=api_key, base_url=base_url, **extra)
        self._tracing = tracing
        self._metadata_lookup_url = metadata_lookup_url

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        raw_messages = OpenAIMessageConverter.to_openai(messages)
        self._sanitize_outbound_names(raw_messages)

        with self._tracing.trace_llm(
            model=self._model,
            provider="openai_compatible",
            input_messages=[
                {"role": m.role.value, "content": m.content}
                for m in messages[-5:]
            ],
        ) as gen:
            try:
                response = self._client.chat.completions.create(
                    model=self._model,
                    messages=raw_messages,
                    temperature=self._temperature,
                    max_completion_tokens=self._max_tokens,
                    tools=self._tools or [],
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            result_msg = OpenAIMessageConverter.from_openai(
                response.choices[0].message,
            )
            result_msg = restore_tool_names(self._rev_names, result_msg)
            result_msg = self._with_response_metadata(
                result_msg,
                build_response_metadata(
                    getattr(response, "id", None),
                    getattr(response, "model", None),
                    extract_extra_fields(response),
                    self._metadata_lookup_url,
                ),
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
        raw_messages = OpenAIMessageConverter.to_openai(messages)
        self._sanitize_outbound_names(raw_messages)
        aggregator = StreamToolCallAggregator()
        collector = StreamMetadataCollector()
        accumulated_content = ""

        with self._tracing.trace_llm(
            model=self._model,
            provider="openai_compatible",
            input_messages=[
                {"role": m.role.value, "content": m.content}
                for m in messages[-5:]
            ],
            metadata={"streaming": True},
        ) as gen:
            try:
                stream_iter = self._client.chat.completions.create(
                    model=self._model,
                    messages=raw_messages,
                    temperature=self._temperature,
                    max_completion_tokens=self._max_tokens,
                    tools=self._tools or [],
                    stream=True,
                    **call_params,
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            for chunk in stream_iter:
                collector.absorb(chunk)
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

        response_metadata = build_response_metadata(
            collector.response_id,
            collector.model,
            collector.fields,
            self._metadata_lookup_url,
        )
        if aggregator.has_tool_calls or response_metadata:
            # A final message is emitted for plain-text streams only when
            # response metadata exists; otherwise the stream is unchanged.
            result = ChatMessage(
                role=Role.ASSISTANT,
                content=accumulated_content,
                tool_calls=aggregator.build() if aggregator.has_tool_calls else None,
                metadata=response_metadata,
            )
            yield restore_tool_names(self._rev_names, result)

    def bind_tools(self, tools: List[ToolDefinition]) -> OpenAICompatibleLLM:
        clone = copy.copy(self)
        clone._fwd_names, clone._rev_names = build_name_maps(
            t.name for t in tools
        )
        clone._tools = OpenAIToolsConverter.to_openai(tools)
        self._sanitize_tool_defs(clone._tools, clone._fwd_names)
        return clone

    @staticmethod
    def _with_response_metadata(
        msg: ChatMessage, response_metadata: Dict[str, Any],
    ) -> ChatMessage:
        """Return *msg* carrying *response_metadata* (unchanged when empty)."""
        if not response_metadata:
            return msg
        return msg.model_copy(update={"metadata": {**msg.metadata, **response_metadata}})

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Name sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_tool_defs(
        tools: Optional[List[ChatCompletionToolParam]],
        fwd_names: Dict[str, str],
    ) -> None:
        """Sanitize function names inside Chat Completions tool defs (in-place)."""
        if not tools:
            return
        for tool in tools:
            name = tool["function"]["name"]
            tool["function"]["name"] = map_name(name, fwd_names)

    def _sanitize_outbound_names(self, messages: List[Dict[str, Any]]) -> None:
        """Sanitize tool-call names in outbound messages (in-place)."""
        for msg in messages:
            for tc in msg.get("tool_calls", []):
                name = tc["function"]["name"]
                tc["function"]["name"] = map_name(name, self._fwd_names)

