from typing import Any, Dict, List, Optional, Iterator, Union
import copy
from langchain_google_genai import ChatGoogleGenerativeAI
from ..common.base_llm import BaseLLM
from core.contracts import SupportsStreaming
from ..common.chat.converter import LangChainConverter
from ..common.chat.message import ChatMessage
from ...tools.common.base_tool import BaseTool
from ...tools.common.converter import LangChainToolsConverter


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
        # Extract text from content blocks
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

        # Build kwargs, only including non-None values
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

        # Convert to LangChain message objects
        lc_messages = LangChainConverter.to_lc(messages)

        response = self.client.invoke(lc_messages, **call_params)
        
        # Google GenAI returns content as list of blocks, normalize it to string
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
        # Translate our domain history → LangChain
        lc_history = LangChainConverter.to_lc(messages)

        aggregated: Any | None = None  # will hold the growing AIMessage

        for chunk in self.client.stream(lc_history, **call_params):
            # Tool-call partials -------------------------------------------------
            if getattr(chunk, "tool_call_chunks", None):
                aggregated = chunk if aggregated is None else aggregated + chunk
                # we do NOT yield yet — wait until provider is done
                continue

            # Plain token path --------------------------------------------------
            # Google GenAI returns content as list of blocks, not a simple string
            token = _extract_text_content(chunk.content)
            if token:
                yield token

        # Provider finished ------------------------------------------------------
        if aggregated:
            # LangChain "+" produced a final AIMessage with complete tool_calls,
            # Normalize content format before converting
            if hasattr(aggregated, 'content') and isinstance(aggregated.content, list):
                aggregated.content = _extract_text_content(aggregated.content)
            # Convert once to our ChatMessage model and yield it.
            yield LangChainConverter.from_lc_message(aggregated)

    def bind_tools(self, tools: List[BaseTool]) -> "GoogleGenAILLM":
        """
        Return a new GoogleGenAILLM instance with tools bound, avoiding cross-contamination.

        This creates a copy of the current LLM with tools bound to the client,
        ensuring the original LLM instance remains unchanged.
        """
        # Create a shallow copy of the current instance
        new_llm = copy.copy(self)

        # Create a new client with tools bound (LangChain's bind_tools returns a copy)
        new_llm.client = self.client.bind_tools(LangChainToolsConverter.to_lc(tools))

        return new_llm

    @property
    def name(self) -> str:
        return self._name

