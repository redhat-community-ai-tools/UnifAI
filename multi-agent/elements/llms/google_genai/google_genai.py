from typing import Any, Dict, List, Optional, Iterator, Union
import copy
from langchain_google_genai import ChatGoogleGenerativeAI
from ..common.base_llm import BaseLLM
from core.contracts import SupportsStreaming
from ..common.chat.converter import LangChainConverter
from ..common.chat.message import ChatMessage
from ...tools.common.base_tool import BaseTool
from .tools_converter import GoogleGenAIToolsConverter


def _extract_text_content(content: Any) -> str:
    """
    Extract text from Google GenAI content which can be:
    - A simple string
    - A list of content blocks like [{'type': 'text', 'text': '...'}]
    """
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        return "".join(texts)
    return str(content)


class GoogleGenAILLM(BaseLLM, SupportsStreaming):
    """
    LLM client for Google Generative AI (Gemini) using LangChain's ChatGoogleGenerativeAI wrapper.
    """

    def __init__(
            self,
            model_name: str,
            api_key: str,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            top_p: Optional[float] = None,
            top_k: Optional[int] = None,
            **extra: Any
    ):
        """
        :param model_name:   Gemini model ID (e.g. "gemini-2.0-flash", "gemini-2.5-pro").
        :param api_key:      Google API key for Generative AI.
        :param temperature:  Sampling temperature.
        :param max_tokens:   Max tokens to generate (None for model default).
        :param top_p:        Top-p sampling parameter.
        :param top_k:        Top-k sampling parameter.
        :param extra:        Extra kwargs passed to ChatGoogleGenerativeAI.
        """
        self._name = "google-genai"

        client_kwargs: Dict[str, Any] = {
            "model": model_name,
            "google_api_key": api_key,
            "temperature": temperature,
            **extra
        }

        if max_tokens is not None:
            client_kwargs["max_output_tokens"] = max_tokens
        if top_p is not None:
            client_kwargs["top_p"] = top_p
        if top_k is not None:
            client_kwargs["top_k"] = top_k

        self.client = ChatGoogleGenerativeAI(**client_kwargs)

    def chat(
            self,
            messages: List[ChatMessage],
            *,
            temperature: Optional[float] = None,
            max_tokens: Optional[int] = None,
            stream: bool = False,
            **kwargs: Any
    ) -> ChatMessage:
        """
        Send a chat request to the Gemini model.

        :param messages: List of ChatMessage objects
        :param temperature: Override sampling temperature
        :param max_tokens: Override max tokens
        :param stream: Whether to stream (handled separately)
        :param kwargs: Additional parameters
        """
        call_params: Dict[str, Any] = {}
        if temperature is not None:
            call_params["temperature"] = temperature
        if max_tokens is not None:
            call_params["max_output_tokens"] = max_tokens
        call_params.update(kwargs)

        lc_messages = LangChainConverter.to_lc(messages)
        response = self.client.invoke(lc_messages, **call_params)

        if hasattr(response, 'content') and isinstance(response.content, list):
            response.content = _extract_text_content(response.content)

        return LangChainConverter.from_lc_message(response)

    def stream(
            self,
            messages: List[ChatMessage],
            **call_params: Any,
    ) -> Iterator[Union[str, ChatMessage]]:
        """
        Provider-level streaming:

        • Yields `str` tokens for regular answers.
        • Aggregates *all* `tool_call_chunks` via the LangChain "+" operator
          and, at the very end, yields **one** `ChatMessage` representing
          the full assistant reply with `tool_calls=[…]`.
        """
        lc_history = LangChainConverter.to_lc(messages)
        aggregated: Any | None = None

        for chunk in self.client.stream(lc_history, **call_params):
            if getattr(chunk, "tool_call_chunks", None):
                aggregated = chunk if aggregated is None else aggregated + chunk
                continue

            token = _extract_text_content(chunk.content)
            if token:
                yield token

        if aggregated:
            if hasattr(aggregated, 'content') and isinstance(aggregated.content, list):
                aggregated.content = _extract_text_content(aggregated.content)
            yield LangChainConverter.from_lc_message(aggregated)

    def bind_tools(self, tools: List[BaseTool]) -> "GoogleGenAILLM":
        """
        Return a new GoogleGenAILLM instance with tools bound.

        Uses GoogleGenAIToolsConverter which sanitizes schemas to meet
        Google GenAI's strict validation requirements.
        """
        new_llm = copy.copy(self)
        new_llm.client = self.client.bind_tools(GoogleGenAIToolsConverter.to_lc(tools))
        return new_llm

    @property
    def name(self) -> str:
        return self._name
