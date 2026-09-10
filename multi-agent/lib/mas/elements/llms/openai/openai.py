"""
OpenAI LLM implementation using the Responses API (``/v1/responses``).

This provider targets the official OpenAI endpoint and GPT-5+ / o-series
models that require the Responses API for tool calling.  For older models
or OpenAI-compatible servers (vLLM, LocalAI, Ollama), use the
``openai_compatible`` provider instead.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, Iterator, List, Optional, Union

from openai import OpenAI

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage, Role
from ..common.name_sanitizer import build_name_maps, map_name
from ...tools.common.tool_definition import ToolDefinition
from .responses_adapter import ResponsesAdapter
from .responses_stream_aggregator import ResponsesStreamAggregator
from mas.core.tracing import TracingService


class OpenAILLM(BaseLLM):
    """LLM client for the OpenAI Responses API (GPT-5+, o-series).

    Responsibilities are split across dedicated collaborators:

    * **ResponsesAdapter** – bidirectional ``ChatMessage`` ↔ Responses API format
    * **ResponsesStreamAggregator** – reassembles Responses API streaming events

    Tool names containing dots (e.g. ``time.get_current_time``) are
    sanitized to underscores at the API boundary and restored on
    inbound tool calls.  The adapter handles name sanitization for
    outbound messages; this class handles tool definitions and inbound.
    """

    def __init__(
        self,
        base_url: str,
        model_name: str,
        max_tokens: int = 4096,
        api_key: str = "EMPTY",
        reasoning_effort: Optional[str] = None,
        tracing: TracingService = None,
        **extra: Any,
    ) -> None:
        self._name = "openai"
        self._model = model_name
        self._max_tokens = max_tokens
        self._reasoning_effort = reasoning_effort
        self._responses_tools: Optional[List[Dict[str, Any]]] = None
        self._fwd_names: Dict[str, str] = {}
        self._rev_names: Dict[str, str] = {}
        self._client = OpenAI(api_key=api_key, base_url=base_url, **extra)
        self._tracing = tracing

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        input_items = ResponsesAdapter.to_input(messages, self._fwd_names)

        with self._tracing.trace_llm(
            model=self._model,
            provider="openai",
            input_messages=[
                {"role": m.role.value, "content": m.content}
                for m in messages[-5:]
            ],
        ) as gen:
            try:
                response = self._client.responses.create(
                    **self._build_request(input_items),
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            result_msg = ResponsesAdapter.from_response(response)
            result_msg = self._restore_tool_names(result_msg)
            usage = {}
            if response.usage:
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
            gen.update(output=result_msg.content, usage_details=usage or None)
        return result_msg

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        input_items = ResponsesAdapter.to_input(messages, self._fwd_names)
        aggregator = ResponsesStreamAggregator()

        with self._tracing.trace_llm(
            model=self._model,
            provider="openai",
            input_messages=[
                {"role": m.role.value, "content": m.content}
                for m in messages[-5:]
            ],
            metadata={"streaming": True},
        ) as gen:
            try:
                stream_iter = self._client.responses.create(
                    **self._build_request(input_items, stream=True, **call_params),
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"OpenAI API error: {type(e).__name__}: {e}",
                )
                raise
            for event in stream_iter:
                text_delta = aggregator.process(event)
                if text_delta:
                    yield text_delta

            if aggregator.usage:
                gen.update(usage_details=aggregator.usage)
            gen.update(output=aggregator.accumulated_content)

        if aggregator.has_tool_calls:
            result = ChatMessage(
                role=Role.ASSISTANT,
                content=aggregator.accumulated_content,
                tool_calls=aggregator.build(),
            )
            yield self._restore_tool_names(result)

    def bind_tools(self, tools: List[ToolDefinition]) -> OpenAILLM:
        clone = copy.copy(self)
        clone._fwd_names, clone._rev_names = build_name_maps(
            t.name for t in tools
        )
        clone._responses_tools = ResponsesAdapter.tools_to_responses(tools)
        self._sanitize_tool_defs(clone._responses_tools, clone._fwd_names)
        return clone

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_request(
        self,
        input_items: List[Dict[str, Any]],
        *,
        stream: bool = False,
        **overrides: Any,
    ) -> Dict[str, Any]:
        """Assemble kwargs for ``client.responses.create``."""
        request: Dict[str, Any] = {
            "model": self._model,
            "input": input_items,
            "max_output_tokens": self._max_tokens,
            "tools": self._responses_tools or [],
        }
        if stream:
            request["stream"] = True
        if self._reasoning_effort:
            request["reasoning"] = {"effort": self._reasoning_effort}
        if overrides:
            request.update(overrides)
        return request

    # ------------------------------------------------------------------
    # Name sanitization
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_tool_defs(
        tools: Optional[List[Dict[str, Any]]],
        fwd_names: Dict[str, str],
    ) -> None:
        """Sanitize function names inside Responses API tool defs (in-place)."""
        if not tools:
            return
        for tool in tools:
            tool["name"] = map_name(tool["name"], fwd_names)

    def _restore_tool_names(self, msg: ChatMessage) -> ChatMessage:
        """Map provider-safe names back to domain names on an inbound message."""
        if not msg.tool_calls:
            return msg
        restored = [
            tc.model_copy(update={"name": map_name(tc.name, self._rev_names)})
            for tc in msg.tool_calls
        ]
        return msg.model_copy(update={"tool_calls": restored})
