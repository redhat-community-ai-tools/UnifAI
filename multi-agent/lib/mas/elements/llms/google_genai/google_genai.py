"""
Google GenAI (Gemini) LLM implementation using the native ``google-genai`` SDK.

Supports Gemini models via the Google AI Studio API key.
"""

from __future__ import annotations

import copy
import logging
from typing import Any, Iterator, List, Optional, Union

from google import genai
from google.genai import types

from ..common.base_llm import BaseLLM
from ..common.chat.message import ChatMessage
from ...tools.common.tool_definition import ToolDefinition
from .message_converter import GoogleGenAIMessageConverter
from .tools_converter import GoogleGenAIToolsConverter

logger = logging.getLogger(__name__)

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

    # ------------------------------------------------------------------
    # BaseLLM interface
    # ------------------------------------------------------------------

    def chat(self, messages: List[ChatMessage]) -> ChatMessage:
        split = GoogleGenAIMessageConverter.to_genai(messages)
        config = self._build_config(system_instruction=split.system_instruction)

        response = self._client.models.generate_content(
            model=self._model,
            contents=split.contents,
            config=config,
        )
        return GoogleGenAIMessageConverter.from_genai(response)

    def stream(
        self,
        messages: List[ChatMessage],
        **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        split = GoogleGenAIMessageConverter.to_genai(messages)
        config = self._build_config(system_instruction=split.system_instruction)

        accumulated_text = ""
        collected_parts: List[types.Part] = []
        yielded = False

        for chunk in self._client.models.generate_content_stream(
            model=self._model,
            contents=split.contents,
            config=config,
        ):
            if chunk.text:
                accumulated_text += chunk.text
                yield chunk.text
                yielded = True

            for part in (chunk.parts or []):
                if part.function_call is not None:
                    collected_parts.append(part)

        if collected_parts:
            yield GoogleGenAIMessageConverter.from_genai_parts(
                collected_parts, accumulated_text,
            )
            yielded = True

        if not yielded:
            logger.warning("Google GenAI stream returned no content and no tool calls (model=%s)", self._model)
            yield ""

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
