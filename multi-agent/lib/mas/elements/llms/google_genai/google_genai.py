"""
Google GenAI (Gemini) LLM implementation using the native ``google-genai`` SDK.

Supports Gemini models via the Google AI Studio API key.
"""

from __future__ import annotations

import copy
from typing import Any, Iterator, List, Optional, Union

from google import genai
from google.genai import types

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import GoogleGenAIMessageConverter
from .tools_converter import GoogleGenAIToolsConverter

_DISABLE_AUTO_FC = types.AutomaticFunctionCallingConfig(disable=True)


class GoogleGenAILLM(BaseLLM):
    """LLM client backed by the native Google GenAI Python SDK.

    Responsibilities are split across dedicated collaborators:

    * **GoogleGenAIMessageConverter** – bidirectional ``ChatMessage`` ↔ ``types.Content``
    * **GoogleGenAIToolsConverter** – ``BaseTool`` → ``types.Tool`` / ``types.FunctionDeclaration``
    * **SchemaSanitizer** – strips patterns rejected by Google's strict schema validation
    """

    def __init__(
        self,
        model_name: str,
        api_key: str,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        tracing: Any = None,
        **extra: Any,
    ) -> None:
        self._name = "google-genai"
        self._model = model_name
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._top_p = top_p
        self._top_k = top_k
        self._tools: Optional[List[types.Tool]] = None
        self._client = genai.Client(api_key=api_key, **extra)
        if not tracing:
            from mas.core.tracing.noop import NoOpTracingService
            tracing = NoOpTracingService()
        self._tracing = tracing

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        split = GoogleGenAIMessageConverter.to_genai(messages)
        config = self._build_config(system_instruction=split.system_instruction)

        with self._tracing.trace_llm(
            model=self._model,
            provider="google-genai",
            input_messages=[{"role": m.role.value, "content": m.content} for m in messages[-5:]],
        ) as gen:
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=split.contents,
                    config=config,
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"Google GenAI API error: {type(e).__name__}: {e}",
                )
                raise
            result_msg = GoogleGenAIMessageConverter.from_genai(response)
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
                um = response.usage_metadata
                usage = {
                    "input_tokens": getattr(um, "prompt_token_count", 0),
                    "output_tokens": getattr(um, "candidates_token_count", 0),
                    "total_tokens": getattr(um, "total_token_count", 0),
                }
            gen.update(output=result_msg.content, usage_details=usage or None)
        return result_msg

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        split = GoogleGenAIMessageConverter.to_genai(messages)
        config = self._build_config(system_instruction=split.system_instruction)

        accumulated_text = ""
        collected_parts: List[types.Part] = []
        last_usage_metadata = None

        with self._tracing.trace_llm(
            model=self._model,
            provider="google-genai",
            input_messages=[{"role": m.role.value, "content": m.content} for m in messages[-5:]],
            metadata={"streaming": True},
        ) as gen:
            try:
                stream_iter = self._client.models.generate_content_stream(
                    model=self._model,
                    contents=split.contents,
                    config=config,
                )
            except Exception as e:
                gen.update(
                    level="ERROR",
                    status_message=f"Google GenAI API error: {type(e).__name__}: {e}",
                )
                raise
            for chunk in stream_iter:
                if chunk.text:
                    accumulated_text += chunk.text
                    yield chunk.text

                for part in (chunk.parts or []):
                    if part.function_call is not None:
                        collected_parts.append(part)

                if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                    last_usage_metadata = chunk.usage_metadata

            usage = {}
            if last_usage_metadata:
                usage = {
                    "input_tokens": getattr(last_usage_metadata, "prompt_token_count", 0),
                    "output_tokens": getattr(last_usage_metadata, "candidates_token_count", 0),
                    "total_tokens": getattr(last_usage_metadata, "total_token_count", 0),
                }
            gen.update(output=accumulated_text, usage_details=usage or None)

        if collected_parts:
            yield GoogleGenAIMessageConverter.from_genai_parts(
                collected_parts, accumulated_text,
            )

    def bind_tools(self, tools: List[ToolDefinition]) -> GoogleGenAILLM:
        clone = copy.copy(self)
        clone._tools = GoogleGenAIToolsConverter.to_genai(tools)
        return clone

    @property
    def name(self) -> str:
        return self._name

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_config(
        self,
        *,
        system_instruction: Optional[str] = None,
    ) -> types.GenerateContentConfig:
        """Assemble a ``GenerateContentConfig`` from instance state."""
        config = types.GenerateContentConfig(
            temperature=self._temperature,
            top_p=self._top_p,
            top_k=self._top_k,
        )

        if self._max_tokens is not None:
            config.max_output_tokens = self._max_tokens

        if system_instruction:
            config.system_instruction = system_instruction

        if self._tools:
            config.tools = self._tools
            config.automatic_function_calling = _DISABLE_AUTO_FC

        return config
